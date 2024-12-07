from collections.abc import Callable

import pytest

from smooth_rpc.exceptions import RpcApiVersionMismatchError, RpcDecoratorError, RpcProtocolError
from smooth_rpc.smoothrpc import api, instrument_client_commands
from tests.conftest import MyCommands, StoringAsyncNetwork


def test_client_sync_throws(connection: StoringAsyncNetwork) -> None:
    """Test instrumentation throws if the 'api' decorator is on a function without 'async'."""

    class MyCommandsSync:
        @api()
        def cmd1(self) -> None: ...  # note, no 'async'

    with pytest.raises(RpcDecoratorError):
        instrument_client_commands(connection, 2, MyCommandsSync())


def test_client_invalid_decoration(connection: StoringAsyncNetwork) -> None:
    def broken_decorator(func: Callable) -> Callable:
        func.__is_part_of_smooth_api = "not-the-correct-thing"  # type: ignore[attr-defined]
        return func

    class MyTestCommands:
        @broken_decorator
        async def cmd1(self) -> None: ...

    with pytest.raises(RpcDecoratorError):
        instrument_client_commands(connection, 2, MyTestCommands())


@pytest.mark.asyncio
async def test_client_local_api_mismatch(client_commands: MyCommands) -> None:
    """Test that the client will not call an API endpoint if the version is out of range."""
    with pytest.raises(RpcApiVersionMismatchError):
        await client_commands.inc_one(3)  # inc_one requires API version >= 3


@pytest.mark.asyncio
async def test_client_remote_call(client_commands: MyCommands, connection: StoringAsyncNetwork) -> None:
    """Call cmd2_old remotely (which is named "cmd2" in the API)."""
    expected_result = 42
    await connection.prepare_for_recv(expected_result)
    result = await client_commands.cmd2_old(3)  # cmd2_old corresponds to cmd2 in the API
    assert len(connection) == 1  # Ensure only one request was sent
    assert str(await connection.get_result()) == "cmd2(args=(3,), kwargs={}, api_version=2)"
    assert result == expected_result  # Ensure the result matches the expected response


@pytest.mark.asyncio
async def test_client_remote_call_unpickle_error(client_commands: MyCommands, connection: StoringAsyncNetwork) -> None:
    """Call cmd4 remotely, but it responds with something not de-pickle'able."""
    await connection.prepare_for_recv_raw(b"bork")
    with pytest.raises(RpcProtocolError):
        await client_commands.cmd4()


@pytest.mark.asyncio
async def test_client_remote_exception(client_commands: MyCommands, connection: StoringAsyncNetwork) -> None:
    """Ensure that a remote exception is properly re-thrown."""
    some_exception = RuntimeError("frop")
    await connection.prepare_for_recv(some_exception)  # Simulate a remote exception
    with pytest.raises(RuntimeError):
        await client_commands.cmd2_old(3)


@pytest.mark.asyncio
async def test_client_normal_function(client_commands: MyCommands) -> None:
    """Ensure that non-decorated functions behave normally."""
    result = await client_commands.cmd3()
    assert result == "no api marker"
