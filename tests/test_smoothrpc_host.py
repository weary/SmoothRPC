import asyncio

import pytest

from smooth_rpc.exceptions import (
    RpcDecoratorError,
    RpcInternalError,
    RpcInvalidVersionError,
    RpcNoSuchApiError,
    RpcProtocolError,
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


@pytest.mark.asyncio
async def test_host_register_commands(host: SmoothRPCHost) -> None:
    assert len(host.commands) == 4
    assert all(cmd in host.commands for cmd in ("inc_one", "cmd2", "shutdown", "throwing_func"))
    assert len(host.commands["cmd2"]) == 2
    ranges = [ver for ver, _cmd in host.commands["cmd2"]]
    assert ranges == [VersionRange(3, None), VersionRange(None, 2)]

    # also test adding a commands class without api-marked functions
    class NoCommands: ...

    with pytest.raises(RpcDecoratorError):
        host.register_commands(NoCommands())


@pytest.mark.asyncio
async def test_host_call_invalid_arguments(network: StoringAsyncNetwork, host: SmoothRPCHost) -> None:
    await network.prepare_for_recv(ApiCall("inc_one", api_version=3, args=(), kwargs={}))
    await host._host_one()
    assert isinstance(await network.get_result(), TypeError)


@pytest.mark.asyncio
async def test_host_call_matching_version(network: StoringAsyncNetwork, host: SmoothRPCHost) -> None:
    # with args
    await network.prepare_for_recv(ApiCall("inc_one", api_version=3, args=(1,), kwargs={}))
    await host._host_one()
    assert len(network) == 1
    assert await network.get_result() == 2

    # with kwargs
    await network.prepare_for_recv(ApiCall("inc_one", api_version=3, args=(), kwargs={"i": 1}))
    await host._host_one()
    assert len(network) == 1
    assert await network.get_result() == 2


@pytest.mark.asyncio
async def test_host_call_unknown_function(network: StoringAsyncNetwork, host: SmoothRPCHost) -> None:
    # with args
    await network.prepare_for_recv(ApiCall("some_func", api_version=3, args=(), kwargs={}))
    await host._host_one()
    assert len(network) == 1
    assert isinstance(await network.get_result(), RpcNoSuchApiError)


@pytest.mark.asyncio
async def test_host_call_version_mismatch(network: StoringAsyncNetwork, host: SmoothRPCHost) -> None:
    # with args
    await network.prepare_for_recv(ApiCall("inc_one", api_version=2, args=(), kwargs={}))
    await host._host_one()
    assert len(network) == 1
    assert isinstance(await network.get_result(), RpcInvalidVersionError)


@pytest.mark.asyncio
async def test_host_call_select_on_version(network: StoringAsyncNetwork, host: SmoothRPCHost) -> None:
    # call 'old' cmd2, api_version=2
    await network.prepare_for_recv(ApiCall("cmd2", api_version=2, args=(3,), kwargs={}))
    await host._host_one()
    assert await network.get_result() == "9"

    # call 'new' cmd2, api_version=3
    await network.prepare_for_recv(ApiCall("cmd2", api_version=3, args=(3,), kwargs={}))
    await host._host_one()
    assert await network.get_result() is None


@pytest.mark.asyncio
async def test_host_shutdown_from_main(network: StoringAsyncNetwork, host: SmoothRPCHost) -> None:
    """Test shutdown works eventually from another asyncio task."""

    async def main_loop() -> None:
        await asyncio.sleep(0.1)
        host.shutdown_after_call()
        # do one last call. Expect it to be handled.
        await network.prepare_for_recv(ApiCall("inc_one", api_version=3, args=(1,), kwargs={}))

    # do shutdown. If this test does not terminate the test failed
    await asyncio.gather(host.host_forever(), main_loop())
    # final call should have a result
    assert len(network) == 1
    assert await network.get_result() == 2


@pytest.mark.asyncio
async def test_host_shutdown_from_rpc(network: StoringAsyncNetwork, host: SmoothRPCHost) -> None:
    await network.prepare_for_recv(ApiCall("shutdown", api_version=3, args=(), kwargs={}))

    # start receive loop. Should receive the shutdown and do shutdown.
    await host.host_forever()

    assert len(network) == 1  # the result from the shutdown call
    assert await network.get_result() == "shutdown done"


@pytest.mark.asyncio
async def test_host_internal_errors(network: StoringAsyncNetwork, host: SmoothRPCHost) -> None:
    # not a ApiCall object
    await network.prepare_for_recv("banana")
    await host._host_one()
    assert len(network) == 1
    assert isinstance(await network.get_result(), RpcProtocolError)

    # unserializable result
    await network.prepare_for_recv(ApiCall("throwing_func", api_version=2, args=(), kwargs={}))
    await host._host_one()
    assert isinstance(await network.get_result(), RpcInternalError)
