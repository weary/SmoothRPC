import asyncio
import logging

from example.commands import Commands
from SmoothRPC import init_remote_rpc


async def main() -> None:
    address = "ipc:///tmp/aap"
    commands = Commands()
    init_remote_rpc(address, commands, api_version=3)

    out = await commands.hello()
    print(f"commands.hello() returned {out!r}")
    await commands.throw_something("frop")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    asyncio.run(main())
