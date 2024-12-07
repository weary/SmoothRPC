import asyncio

import pytest

from smooth_rpc.exceptions import (
    RpcDecoratorError,
    RpcInternalError,
    RpcInvalidVersionError,
    RpcNoSuchApiError,
    RpcProtocolError,
    RpcSerializationError,
)
from smooth_rpc.smoothrpc import ApiCall, SmoothRPCHost, VersionRange
from tests.test_smoothrpc_client import StoringAsyncNetwork


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

    # invalid type in range-check
    with pytest.raises(RpcInternalError):
        assert "x" in VersionRange(None, None)


@pytest.mark.asyncio
async def test_host_register_commands(host: SmoothRPCHost) -> None:
    expected_commands = ("inc_one", "cmd2", "cmd4", "unserializable")
    assert len(host.commands) == len(expected_commands)
    assert all(cmd in host.commands for cmd in expected_commands)
    assert len(host.commands["cmd2"]) == 2
    ranges = [ver for ver, _cmd in host.commands["cmd2"]]
    assert ranges == [VersionRange(3, None), VersionRange(None, 2)]

    # also test adding a commands class without api-marked functions
    class NoCommands: ...

    with pytest.raises(RpcDecoratorError):
        host.register_commands(NoCommands())


@pytest.mark.asyncio
async def test_host_call_invalid_arguments(connection: StoringAsyncNetwork, host: SmoothRPCHost) -> None:
    await connection.prepare_for_recv(ApiCall("inc_one", api_version=3, args=(), kwargs={}))
    await host._handle_one_command(connection)
    assert isinstance(await connection.get_result(), TypeError)


@pytest.mark.asyncio
async def test_host_call_matching_version(connection: StoringAsyncNetwork, host: SmoothRPCHost) -> None:
    # with args
    await connection.prepare_for_recv(ApiCall("inc_one", api_version=3, args=(1,), kwargs={}))
    await host._handle_one_command(connection)
    assert len(connection) == 1
    assert await connection.get_result() == 2

    # with kwargs
    await connection.prepare_for_recv(ApiCall("inc_one", api_version=3, args=(), kwargs={"i": 1}))
    await host._handle_one_command(connection)
    assert len(connection) == 1
    assert await connection.get_result() == 2


@pytest.mark.asyncio
async def test_host_call_unknown_function(connection: StoringAsyncNetwork, host: SmoothRPCHost) -> None:
    # with args
    await connection.prepare_for_recv(ApiCall("some_func", api_version=3, args=(), kwargs={}))
    await host._handle_one_command(connection)
    assert len(connection) == 1
    assert isinstance(await connection.get_result(), RpcNoSuchApiError)


@pytest.mark.asyncio
async def test_host_call_version_mismatch(connection: StoringAsyncNetwork, host: SmoothRPCHost) -> None:
    # with args
    await connection.prepare_for_recv(ApiCall("inc_one", api_version=2, args=(), kwargs={}))
    await host._handle_one_command(connection)
    assert len(connection) == 1
    assert isinstance(await connection.get_result(), RpcInvalidVersionError)


@pytest.mark.asyncio
async def test_host_call_select_on_version(connection: StoringAsyncNetwork, host: SmoothRPCHost) -> None:
    # call 'old' cmd2, api_version=2
    await connection.prepare_for_recv(ApiCall("cmd2", api_version=2, args=(3,), kwargs={}))
    await host._handle_one_command(connection)
    assert await connection.get_result() == "9"

    # call 'new' cmd2, api_version=3
    await connection.prepare_for_recv(ApiCall("cmd2", api_version=3, args=(3,), kwargs={}))
    await host._handle_one_command(connection)
    assert await connection.get_result() is None


@pytest.mark.asyncio
async def test_host_accept_connection(host: SmoothRPCHost) -> None:
    server = await asyncio.start_server(host.accept_connection, "localhost", 0)
    port = server.sockets[0].getsockname()[1]  # Get the assigned port

    # connect normally, no commands issued
    _, writer = await asyncio.open_connection("localhost", port)
    await asyncio.sleep(0)
    writer.close()
    await writer.wait_closed()

    # connect with partial write. Will close with exception
    _, writer = await asyncio.open_connection("localhost", port)
    writer.write(b"x")
    await asyncio.sleep(0)
    writer.close()
    await writer.wait_closed()

    server.close()
    # await server.wait_closed()  # hangs, appears to be a bug in the python standard library
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_host_internal_errors(connection: StoringAsyncNetwork, host: SmoothRPCHost) -> None:
    # not a ApiCall object
    await connection.prepare_for_recv("banana")
    with pytest.raises(RpcProtocolError):
        await host._handle_one_command(connection)

    # not deserializable request
    await connection.prepare_for_recv_raw(b"bork")
    with pytest.raises(RpcProtocolError):
        await host._handle_one_command(connection)

    # unserializable result
    await connection.prepare_for_recv(ApiCall("unserializable", api_version=2, args=(), kwargs={}))
    await host._handle_one_command(connection)
    out = await connection.get_result()
    assert isinstance(out, RpcSerializationError)
