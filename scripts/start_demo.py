"""One process owns the management server, which cleans up its own node children."""
import argparse
import asyncio
import os
from pathlib import Path
import socket
import sys

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


async def run(host: str, port: int):
    from backend.app.main import app
    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="info"))
    # Bind before creating a background task so port conflicts produce a useful
    # error instead of Uvicorn's SystemExit escaping an asyncio task.
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.bind((host, port))
        listener.listen(socket.SOMAXCONN)
        listener.setblocking(False)
    except BaseException:
        listener.close()
        raise
    task = asyncio.create_task(server.serve(sockets=[listener]))
    try:
        while not server.started:
            if task.done():
                await task
                return
            await asyncio.sleep(0.05)
        await app.state.simulation.start()
        print(f"\nDashboard: http://{'127.0.0.1' if host == '0.0.0.0' else host}:{port}\n", flush=True)
        await task
    finally:
        server.should_exit = True
        if not task.done():
            await task
        listener.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.getenv("RA_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("RA_PORT", "8000")))
    args = parser.parse_args()
    if not (ROOT / "frontend/dist/index.html").exists():
        raise SystemExit("Build frontend first: cd frontend; npm.cmd install; npm.cmd run build")
    try:
        asyncio.run(run(args.host, args.port))
    except KeyboardInterrupt:
        pass
    except OSError as exc:
        raise SystemExit(f"Cannot open {args.host}:{args.port}: {exc}. Try --port 8010.") from None
