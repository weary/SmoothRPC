import logging
import time

from async_zmq_rpc import AsyncZmqRpc, api

_log = logging.getLogger(__name__)


class MyError(Exception): ...


class Commands(AsyncZmqRpc):
    @api
    async def hello(self) -> str:
        _log.info("Processing hello command")
        time.sleep(1)
        return "World"

    @api
    async def throw_something(self, arg: str) -> None:
        _log.info("Processing throw_something command")
        raise MyError("Throwing something", arg)

    async def not_callable(self) -> None:
        print("arg!")
