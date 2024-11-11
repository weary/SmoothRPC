from SmoothRPC.exceptions import RpcError
from SmoothRPC.network import AsyncZmqNetworkClient, AsyncZmqNetworkHost
from SmoothRPC.smoothrpc import SmoothRPCClient, SmoothRPCHost, api

__all__ = [
    "api",
    "host_forever",
    "init_remote_rpc",
    "RpcError",
    "SmoothRPCClient",
    "SmoothRPCHost",
]


async def host_forever(address: str, *commands: tuple) -> None:
    """Host all rpc-marked functions from commands on address."""
    network = AsyncZmqNetworkHost(address)
    rpc = SmoothRPCHost(network)
    rpc.register_commands(commands)
    await rpc.host_forever()


def init_remote_rpc(address: str, *commands: tuple, api_version: int) -> None:
    """
    Replace all rpc-marked functions from commands with remote calls to address.

    A connection to address is opened.
    """
    network = AsyncZmqNetworkClient(address)
    client = SmoothRPCClient(network)
    for arg in commands:
        client.instrument(arg, api_version=api_version)
