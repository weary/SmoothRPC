"""Carrier network for SmoothRPC, uses ZMQ."""

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
        """Create a network instance and bind to address."""
        context = zmq.asyncio.Context()
        _log.info(f"Listening on {address}…")
        self.socket = context.socket(zmq.REP)
        self.socket.bind(address)

    async def send_pyobj(self, pyobj: object) -> None:
        """Send an object to the client."""
        await self.socket.send_pyobj(pyobj)

    async def recv_pyobj(self) -> object:
        """Receive an object from the client."""
        return await self.socket.recv_pyobj()


class AsyncZmqNetworkClient(AsyncNetwork):
    """Client network implementation using ZeroMQ."""

    def __init__(self, address: str) -> None:
        """Create a network instance and connect to address."""
        context = zmq.asyncio.Context()
        _log.info(f"Connecting to {address}…")
        self.socket = context.socket(zmq.REQ)
        self.socket.connect(address)

    async def send_pyobj(self, pyobj: object) -> None:
        """Send an object to the host."""
        await self.socket.send_pyobj(pyobj)

    async def recv_pyobj(self) -> object:
        """Receive an object from the host."""
        return await self.socket.recv_pyobj()