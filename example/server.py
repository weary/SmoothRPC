import asyncio
import logging

from myproject.commands import Commands


async def main() -> None:
    url = "ipc:///tmp/aap"
    commands = Commands(address=url, is_server=True)
    await commands.serve_forever()
    # await asyncio.gather(server_func("tcp://localhost:5555"), server_func())


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main())
