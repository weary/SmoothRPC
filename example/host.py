"""SmoothRPC host example."""

import asyncio
import logging

from example.commands import ExampleCommands
from smooth_rpc import host_forever


async def main() -> None:
    """Host the example API on a unix socket."""
    address = "ipc:///tmp/aap"

    command_instance = ExampleCommands()
    await host_forever(address, command_instance)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main())
