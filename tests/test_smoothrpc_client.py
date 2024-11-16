from collections.abc import Callable

import pytest

from smooth_rpc.exceptions import RpcApiVersionMismatchError, RpcDecoratorError
from smooth_rpc.smoothrpc import SmoothRPCClient, api
from tests.conftest import MyCommands, StoringAsyncNetwork


def test_client_sync_throws(network: StoringAsyncNetwork) -> None:
    """Test instrumentation throws if the 'api' decorator is on a function without 'async'."""

    class MyCommandsSync:
        @api()
        def cmd1(self) -> None: ...  # note, no 'async'

    client = SmoothRPCClient(network)

    with pytest.raises(RpcDecoratorError):
        client.instrument(MyCommandsSync(), api_version=2)


def test_client_invalid_decoration(network: StoringAsyncNetwork) -> None:
    def broken_decorator(func: Callable) -> Callable:
        func.is_part_of_smooth_api = "not-the-correct-thing"
        return func

    class MyTestCommands:
        @broken_decorator
        async def cmd1(self) -> None: ...

    client = SmoothRPCClient(network)

    with pytest.raises(RpcDecoratorError):
        client.instrument(MyTestCommands(), api_version=2)


@pytest.mark.asyncio
async def test_client_local_api_mismatch(client_commands: MyCommands) -> None:
    """Test that the client will not call an API endpoint if the version is out of range."""
    with pytest.raises(RpcApiVersionMismatchError):
        await client_commands.inc_one(3)  # inc_one requires API version >= 3


@pytest.mark.asyncio
async def test_client_remote_call(client_commands: MyCommands, network: StoringAsyncNetwork) -> None:
    """Call cmd2_old remotely (which is named "cmd2" in the API)."""
    expected_result = 42
    await network.prepare_for_recv(expected_result)  # Simulate a response from the network
    result = await client_commands.cmd2_old(3)  # cmd2_old corresponds to cmd2 in the API
    assert len(network) == 1  # Ensure only one request was sent
    assert str(await network.get_result()) == "cmd2(args=(3,), kwargs={}, api_version=2)"
    assert result == expected_result  # Ensure the result matches the expected response


@pytest.mark.asyncio
async def test_client_remote_exception(client_commands: MyCommands, network: StoringAsyncNetwork) -> None:
    """Ensure that a remote exception is properly re-thrown."""
    some_exception = RuntimeError("frop")
    await network.prepare_for_recv(some_exception)  # Simulate a remote exception
    with pytest.raises(RuntimeError):
        await client_commands.cmd2_old(3)


@pytest.mark.asyncio
async def test_client_normal_function(client_commands: MyCommands) -> None:
    """Ensure that non-decorated functions behave normally."""
    result = await client_commands.cmd3()
    assert result == "no api marker"
