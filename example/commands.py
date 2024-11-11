import logging
import time

from SmoothRPC.smoothrpc import api

_log = logging.getLogger(__name__)


class MyError(Exception): ...


class Commands:
    @api(func_name="frop")
    async def hello(self) -> str:
        _log.info("Processing hello command")
        time.sleep(1)
        return "World"

    @api(min_version=3)
    async def throw_something(self, arg: str) -> None:
        _log.info("Processing throw_something command")
        raise MyError("Throwing something", arg)

    @api(func_name="throw_something", max_version=2)
    async def throw_something_old(self, arg: str) -> None:
        _log.info("Processing OLD throw_something command")
        raise MyError("Throwing something old", arg)

    async def not_callable(self) -> None:
        print("arg!")
