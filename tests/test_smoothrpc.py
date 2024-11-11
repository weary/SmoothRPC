import pickle

import pytest

from SmoothRPC import init_remote_rpc
from SmoothRPC.exceptions import RpcApiVersionMismatchError, RpcDecoratorError, RpcInvalidVersionError
from SmoothRPC.network import AsyncNetwork
from SmoothRPC.smoothrpc import SmoothRPCClient, VersionRange, api


def test_version_range() -> None:
    # open ended range contains everything
    assert 3 in VersionRange(None, None)

    # with max
    max_range = VersionRange(None, 5)
    assert 5 in max_range
    assert 6 not in max_range

    # with min
    min_range = VersionRange(4, None)
    assert 3 not in min_range
    assert 4 in min_range

    # with min and max
    full_range = VersionRange(4, 5)
    assert 3 not in full_range
    assert 4 in full_range
    assert 5 in full_range
    assert 6 not in full_range


class StoringAsyncNetwork(AsyncNetwork):
    def __init__(self, recv_objs: list) -> None:
        self.recv_objs = recv_objs
        self.send_objs: list = []

    async def send_pyobj(self, pyobj: object) -> None:
        self.send_objs.append(pyobj)

    async def recv_pyobj(self) -> object:
        return self.recv_objs.pop(0)


class MyCommandsSync:
    @api()
    def cmd1(self) -> None:
        assert False


def test_client_sync_throws() -> None:
    network = StoringAsyncNetwork([])
    client = SmoothRPCClient(network)
    with pytest.raises(RpcDecoratorError):
        client.instrument(MyCommandsSync(), api_version=2)


class MyCommands:
    @api(min_version=3)
    async def cmd1(self, i: int) -> None:
        assert False

    @api(min_version=3)
    async def cmd2(self, i: int) -> None:
        assert False

    @api(func_name="cmd2", max_version=2)
    async def cmd2_old(self, i: int) -> str:
        assert False

    async def cmd3(self) -> str:
        return "no api marker"


@pytest.mark.asyncio
async def test_client() -> None:
    commands = MyCommands()
    network = StoringAsyncNetwork([])
    client = SmoothRPCClient(network)
    client.instrument(commands, api_version=2)

    # test invalid api versions raises local exception
    with pytest.raises(RpcApiVersionMismatchError):
        await commands.cmd1(3)

    # test normal call
    network.recv_objs = [42]
    result = await commands.cmd2_old(3)  # actually is named "cmd2"
    assert len(network.send_objs) == 1
    assert str(network.send_objs[0]) == "cmd2(args=(3,), kwargs={}, api_version=2)"
    assert result == 42

    # test remote exception is re-thrown
    some_exception = RuntimeError("frop")
    network.recv_objs = [some_exception]
    with pytest.raises(RuntimeError):
        await commands.cmd2_old(3)

    # test non-decorated function does nothing special
    assert await commands.cmd3() == "no api marker"
