"""Commands used in example host/client for SmoothRPC."""

import asyncio
import logging

from smooth_rpc.smoothrpc import api

_log = logging.getLogger(__name__)


class MyError(Exception):
    """Dummy error to demonstrate API."""


class ExampleCommands:
    """Some example API commands."""

    @api(func_name="frop")
    async def hello(self) -> str:
        """Return "World" after doing some work."""
        _log.info("Processing hello command")
        await asyncio.sleep(1)  # some work
        return "World"

    @api(min_version=3)
    async def throw_something(self, arg: str) -> None:
        """Throw an exception."""
        _log.info("Processing throw_something command")
        raise MyError("Throwing something", arg)

    @api(func_name="throw_something", max_version=2)
    async def throw_something_old(self, arg: str) -> None:
        """Throw an exception, deprecated API from version 2."""
        _log.info("Processing OLD throw_something command")
        raise MyError("Throwing something old", arg)

    async def not_callable(self) -> None:
        """Undecorated function, will just be executed locally."""
        print("arg!")
