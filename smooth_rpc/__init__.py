"""SmoothRPC Module."""

from smooth_rpc.exceptions import RpcError
from smooth_rpc.network import AsyncZmqNetworkClient, AsyncZmqNetworkHost
from smooth_rpc.smoothrpc import SmoothRPCClient, SmoothRPCHost, api

__all__ = [
    "api",
    "host_forever",
    "init_remote_rpc",
    "RpcError",
    "SmoothRPCClient",
    "SmoothRPCHost",
]


async def host_forever(address: str, *commands: object) -> None:  # pragma: no cover
    """
    Listen on 'address and host all rpc-marked functions from commands.

    Note that this is a convenience function, that does not support stopping the host.
    """
    network = AsyncZmqNetworkHost(address)
    rpc = SmoothRPCHost(network)
    for command_object in commands:
        rpc.register_commands(command_object)
    await rpc.host_forever()


def init_remote_rpc(address: str, *commands: object, api_version: int = 1) -> None:  # pragma: no cover
    """
    Replace all rpc-marked functions from commands with remote calls to address.

    A connection to 'address' is opened.
    """
    network = AsyncZmqNetworkClient(address)
    client = SmoothRPCClient(network)
    for arg in commands:
        client.instrument(arg, api_version=api_version)
