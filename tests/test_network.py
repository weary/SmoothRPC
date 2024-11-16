import asyncio

import pytest

from smooth_rpc.network import AsyncZmqNetworkClient, AsyncZmqNetworkHost


@pytest.mark.asyncio
async def test_zmq_network_loopback() -> None:
    address = "tcp://127.0.0.1:5555"
    server = AsyncZmqNetworkHost(address)
    client = AsyncZmqNetworkClient(address)

    test_object = {"test": "object"}
    c2s = await asyncio.gather(
        client.send_pyobj(test_object),
        server.recv_pyobj(),
    )
    assert c2s == [None, test_object]
    s2c = await asyncio.gather(
        server.send_pyobj(test_object),
        client.recv_pyobj(),
    )
    assert s2c == [None, test_object]
