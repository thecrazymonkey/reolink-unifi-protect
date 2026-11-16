"""--heartbeat-file: a liveness signal that follows the event loop, not the
camera or the NVR."""

import asyncio
import os

from unifi.main import heartbeat


async def test_heartbeat_touches_file_repeatedly(tmp_path):
    path = tmp_path / "heartbeat"
    task = asyncio.create_task(heartbeat(str(path), interval=0.01))
    try:
        await asyncio.sleep(0.05)
        assert path.exists()
        os.utime(path, (0, 0))
        await asyncio.sleep(0.05)
        assert path.stat().st_mtime > 0
    finally:
        task.cancel()


async def test_heartbeat_survives_unwritable_path(tmp_path):
    task = asyncio.create_task(
        heartbeat(str(tmp_path / "missing" / "heartbeat"), interval=0.01)
    )
    await asyncio.sleep(0.05)
    assert not task.done()
    task.cancel()
