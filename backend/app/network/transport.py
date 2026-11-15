"""One newline-delimited JSON frame per RPC; responses acknowledge receipt only."""
import asyncio
import json
from typing import Any

MAX_FRAME = 262144


async def rpc(host: str, port: int, payload: dict, timeout: float = 2.0) -> dict[str, Any]:
    writer = None
    try:
        async with asyncio.timeout(timeout):
            reader, writer = await asyncio.open_connection(host, port, limit=MAX_FRAME)
            writer.write(json.dumps(payload, ensure_ascii=False).encode() + b"\n")
            await writer.drain()
            data = await reader.readline()
            if not data or not data.endswith(b"\n"):
                raise ConnectionError("Incomplete response frame")
            response = json.loads(data)
            if not isinstance(response, dict):
                raise ValueError("Response must be an object")
            return response
    finally:
        if writer:
            writer.close()
            await writer.wait_closed()
