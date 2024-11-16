"""SmoothRPC client example."""

import asyncio
import logging

from example.commands import ExampleCommands, MyError
from smooth_rpc import init_remote_rpc


async def main() -> None:
    """Use the example API."""
    address = "ipc:///tmp/aap"
    commands = ExampleCommands()
    init_remote_rpc(address, commands, api_version=3)

    out = await commands.hello()
    print(f"commands.hello() returned {out!r}")

    try:
        await commands.throw_something("frop")
    except MyError as exc:
        print("This exception was thrown on the host:", exc)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    asyncio.run(main())
