import asyncio
import logging

from myproject.commands import Commands


async def main() -> None:
    url = "ipc:///tmp/aap"
    commands = Commands(address=url, is_server=False)

    out = await commands.hello()
    print(f"commands.hello() returned {out!r}")
    await commands.throw_something("frop")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    asyncio.run(main())
