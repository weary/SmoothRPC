import asyncio

import pytest

from smooth_rpc.network import AsyncNetwork
from smooth_rpc.smoothrpc import SmoothRPCClient, SmoothRPCHost, api


class UnserializableError(Exception):
    """An exception that cannot be sent over the network."""


class StoringAsyncNetwork(AsyncNetwork):
    """Simple implementation of the network for testing."""

    def __init__(self) -> None:
        """Construct a StoringAsyncNetwork."""
        self._recv_objs = asyncio.Queue()
        self._send_objs = asyncio.Queue()

    async def send_pyobj(self, pyobj: object) -> None:
        """Fake-send an object."""
        if isinstance(pyobj, UnserializableError):
            raise pyobj
        await self._send_objs.put(pyobj)

    async def recv_pyobj(self) -> object:
        """Fake-receive an object."""
        return await self._recv_objs.get()

    async def prepare_for_recv(self, pyobj: object) -> None:
        """Place next element to be received by recv_pyobj in queue."""
        await self._recv_objs.put(pyobj)

    async def get_result(self) -> object:
        """Return oldes object that was passed to send_pyobj."""
        return await self._send_objs.get()

    def __len__(self) -> int:
        """Return number of items that were passed to send_pyobj."""
        return self._send_objs.qsize()


class MyCommands:
    """Some test commands."""

    def __init__(self, host: SmoothRPCHost | None) -> None:
        """Create MyCommands, arguments only used on host."""
        self.host = host

    @api(min_version=3)
    async def inc_one(self, i: int) -> int:
        """Command that exists since version 3."""
        assert self.host is not None  # fail if reached on client
        return i + 1

    @api(min_version=3)
    async def cmd2(self, _i: int) -> None:
        """Replace cmd2_old API."""
        assert self.host is not None  # fail if reached on client

    @api(func_name="cmd2", max_version=2)
    async def cmd2_old(self, i: int) -> str:
        """Old 'cmd2', if called with version=2 this should be called instead of 'cmd2'."""
        assert self.host is not None  # fail if reached on client
        return str(i * i)

    async def cmd3(self) -> str:
        """Unmarked by 'api' decorator."""
        return "no api marker"

    @api()
    async def shutdown(self) -> str:
        """Shut down the server remotely."""
        assert self.host is not None  # fail if reached on client
        self.host.shutdown_after_call()
        return "shutdown done"

    @api()
    async def throwing_func(self) -> None:
        """Throw an exception that cannot be (fake)serialized."""
        raise UnserializableError("Something unserializable")


@pytest.fixture
def network() -> StoringAsyncNetwork:
    """Fixture for our dummy network."""
    return StoringAsyncNetwork()


@pytest.fixture
def client_fixture(network: StoringAsyncNetwork) -> MyCommands:
    """Fixture to set up the network and instrumented client."""
    client = SmoothRPCClient(network)
    commands = MyCommands(None)  # arguments unused

    # Instrument the commands with API version 2, so cmd2_old should work, but cmd2 not
    client.instrument(commands, api_version=2)

    return commands


@pytest.fixture
def client_commands(client_fixture: MyCommands) -> MyCommands:
    """Instrumented MyCommands instance."""
    return client_fixture


@pytest.fixture
def host(network: StoringAsyncNetwork) -> SmoothRPCHost:
    """Fixture to set up the network and instrumented host commands."""
    host = SmoothRPCHost(network)
    commands = MyCommands(host)

    host.register_commands(commands)

    return host
