import logging
from abc import ABC, abstractmethod

import zmq
import zmq.asyncio

_log = logging.getLogger(__name__)


class AsyncNetwork(ABC):
    @abstractmethod
    async def send_pyobj(self, pyobj: object) -> None: ...

    @abstractmethod
    async def recv_pyobj(self) -> object: ...

    @abstractmethod
    def shutdown(self) -> None: ...


class AsyncZmqNetwork(AsyncNetwork):
    def __init__(self, address: str, is_server: bool) -> None:
        context = zmq.asyncio.Context()
        if is_server:
            _log.info(f"Listening on {address}…")
            self.socket = context.socket(zmq.REP)
            self.socket.bind(address)
        else:
            _log.info(f"Connecting to {address} server…")
            self.socket = context.socket(zmq.REQ)
            self.socket.connect(address)

    async def send_pyobj(self, pyobj: object) -> None:
        await self.socket.send_pyobj(pyobj)

    async def recv_pyobj(self) -> object:
        return await self.socket.recv_pyobj()

    def shutdown(self) -> None:
        self.socket.close()
