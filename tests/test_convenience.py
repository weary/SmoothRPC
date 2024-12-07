import asyncio
from pathlib import Path

import pytest

from smooth_rpc import host_forever, init_remote_rpc
from tests.conftest import MyCommands


# note, when enabling this test, also remove all 'pragma:no cover' markings
@pytest.mark.asyncio
@pytest.mark.skip(reason="no way to stop the host again")
async def test_smoothrpc_convenience_entrypoints(tmp_path: Path) -> None:  # pragma: no cover
    socket_path = tmp_path / "test_socket"
    address = f"ipc://{socket_path}"
    host_task = asyncio.create_task(host_forever(address, MyCommands(am_i_host=True)))
    await asyncio.sleep(0)

    commands = MyCommands(am_i_host=False)
    _, writer = await init_remote_rpc(address, commands)

    # try to shutdown again
    writer.close()
    await writer.wait_closed()

    host_task.cancel()
    await asyncio.sleep(0)
