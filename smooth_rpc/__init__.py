"""SmoothRPC Module."""

import asyncio
from pathlib import Path

from smooth_rpc.exceptions import RpcAddressError, RpcError
from smooth_rpc.network import AsyncNetworkConnection
from smooth_rpc.smoothrpc import SmoothRPCHost, api, instrument_client_commands

__all__ = [
    "api",
    "AsyncNetworkConnection",
    "host_forever",
    "init_remote_rpc",
    "RpcError",
    "SmoothRPCHost",
]


async def host_forever(address: str, *commands: object) -> None:  # pragma: no cover
    """
    Listen on 'address and host all rpc-marked functions from commands.

    Note that this is a convenience function, that does not support stopping the host.
    """
    rpc = SmoothRPCHost()
    for command_object in commands:
        rpc.register_commands(command_object)

    match address:
        case address if address.startswith("ipc://"):
            path = Path(address[6:])
            host = await asyncio.start_unix_server(rpc.accept_connection, path=path)
        case address if address.startswith("tcp://"):
            # FIXME: test the tcp client
            ip_host, tcp_port = address[6:].split(":", 2)
            host = await asyncio.start_server(rpc.accept_connection, host=ip_host, port=int(tcp_port))
        case _:
            raise RpcAddressError("Unrecognized address", address)

    await host.serve_forever()


async def init_remote_rpc(
    address: str, *commands: object, api_version: int = 1
) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:  # pragma: no cover
    """
    Replace all rpc-marked functions from commands with remote calls to address.

    A connection to 'address' is opened. The connection object is returned, so it
    can be used to explicitly close the connection.
    """
    match address:
        case address if address.startswith("ipc://"):
            path = Path(address[6:])
            reader, writer = await asyncio.open_unix_connection(path=path)
        case address if address.startswith("tcp://"):
            # FIXME: test the tcp client
            ip_host, tcp_port_str = address[6:].split(":", 2)
            tcp_port = int(tcp_port_str)
            reader, writer = await asyncio.open_connection(host=ip_host, port=tcp_port)
        case _:
            raise RpcAddressError("Unrecognized address", address)
    connection = AsyncNetworkConnection(reader, writer)
    instrument_client_commands(connection, api_version, *commands)
    return reader, writer
