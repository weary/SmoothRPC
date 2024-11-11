import asyncio
import logging

from example.commands import Commands
from SmoothRPC import host_forever


async def main() -> None:
    address = "ipc:///tmp/aap"

    commands = Commands()
    await host_forever(address, commands)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main())
