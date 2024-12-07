import asyncio
import pickle

import pytest

from smooth_rpc import SmoothRPCHost, api
from smooth_rpc.network import AsyncNetworkConnection
from smooth_rpc.smoothrpc import instrument_client_commands


class UnserializableError(Exception):
    """An exception that cannot be sent over the network."""


class StoringAsyncNetwork(AsyncNetworkConnection):
    """Simple implementation of the network for testing."""

    def __init__(self) -> None:
        """Construct a StoringAsyncNetwork."""
        self._recv_objs: asyncio.Queue[bytes] = asyncio.Queue()
        self._send_objs: asyncio.Queue[bytes] = asyncio.Queue()

    async def send_message(self, data: bytes) -> None:
        """Fake-send an object."""
        await self._send_objs.put(data)

    async def recv_message(self) -> bytes:
        """Fake-receive an object."""
        return await self._recv_objs.get()

    async def prepare_for_recv_raw(self, data: bytes) -> None:
        """Place next element to be received by recv_message in queue."""
        await self._recv_objs.put(data)

    async def prepare_for_recv(self, pyobj: object) -> None:
        """Place next element to be received by recv_message in queue after pickling."""
        await self.prepare_for_recv_raw(pickle.dumps(pyobj))

    async def get_result_raw(self) -> bytes:
        """Return oldest object that was passed to send_message as raw bytes."""
        return await self._send_objs.get()

    async def get_result(self) -> object:
        """Return oldest object that was passed to send_message unpickled."""
        return pickle.loads(await self.get_result_raw())  # noqa: S301

    def __len__(self) -> int:
        """Return number of items that were passed to send_message."""
        return self._send_objs.qsize()


class MyCommands:
    """Some test commands."""

    def __init__(self, *, am_i_host: bool) -> None:
        """Create MyCommands, arguments only used on host."""
        self.am_i_host = am_i_host

    @api(min_version=3)
    async def inc_one(self, i: int) -> int:
        """Command that exists since version 3."""
        assert self.am_i_host  # fail if reached on client
        return i + 1

    @api(min_version=3)
    async def cmd2(self, _i: int) -> None:
        """Replace cmd2_old API."""
        assert self.am_i_host  # fail if reached on client

    @api(func_name="cmd2", max_version=2)
    async def cmd2_old(self, i: int) -> str:
        """Old 'cmd2', if called with version=2 this should be called instead of 'cmd2'."""
        assert self.am_i_host  # fail if reached on client
        return str(i * i)

    async def cmd3(self) -> str:
        """Unmarked by 'api' decorator."""
        return "no api marker"

    @api()
    async def cmd4(self) -> None:
        """Unrestricted api marker."""

    @api()
    async def unserializable(self) -> object:
        """Throw an exception that cannot be serialized."""

        class LocalClass:
            pass

        return LocalClass()


def data_to_msg(data: bytes) -> bytes:
    out = len(data).to_bytes(8) + data
    assert len(out) == 8 + len(data)
    return out


@pytest.fixture
def connection() -> StoringAsyncNetwork:
    """Fixture for our dummy network."""
    return StoringAsyncNetwork()


@pytest.fixture
def client_commands(connection: StoringAsyncNetwork) -> MyCommands:
    """Fixture to set up the network and instrumented client."""
    # Instrument the commands with API version 2, so cmd2_old should work, but cmd2 not
    api_version = 2
    commands = MyCommands(am_i_host=False)
    instrument_client_commands(connection, api_version, commands)
    return commands


@pytest.fixture
def host() -> SmoothRPCHost:
    """Fixture to set up the network and instrumented host commands."""
    host = SmoothRPCHost()
    commands = MyCommands(am_i_host=True)

    host.register_commands(commands)

    return host
