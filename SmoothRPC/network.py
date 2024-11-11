import logging
from abc import ABC, abstractmethod

import zmq
import zmq.asyncio

_log = logging.getLogger(__name__)


class AsyncNetwork(ABC):
    """Network abstract base class."""

    @abstractmethod
    async def send_pyobj(self, pyobj: object) -> None:
        """Send a python object over the network."""

    @abstractmethod
    async def recv_pyobj(self) -> object:
        """Receive a python object over the network, block if nothing ready."""


class AsyncZmqNetworkHost(AsyncNetwork):
    """Host network implementation using ZeroMQ."""

    def __init__(self, address: str) -> None:
        context = zmq.asyncio.Context()
        _log.info(f"Listening on {address}…")
        self.socket = context.socket(zmq.REP)
        self.socket.bind(address)

    async def send_pyobj(self, pyobj: object) -> None:
        await self.socket.send_pyobj(pyobj)

    async def recv_pyobj(self) -> object:
        return await self.socket.recv_pyobj()


class AsyncZmqNetworkClient(AsyncNetwork):
    """Client network implementation using ZeroMQ."""

    def __init__(self, address: str) -> None:
        context = zmq.asyncio.Context()
        _log.info(f"Connecting to {address}…")
        self.socket = context.socket(zmq.REQ)
        self.socket.connect(address)

    async def send_pyobj(self, pyobj: object) -> None:
        await self.socket.send_pyobj(pyobj)

    async def recv_pyobj(self) -> object:
        return await self.socket.recv_pyobj()
