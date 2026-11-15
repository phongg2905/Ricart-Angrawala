"""Read-only diagnostics for an already running dashboard; does not request CS."""
import argparse
import asyncio
import json
import re

import httpx
import websockets


async def check(url: str) -> None:
    async with httpx.AsyncClient(base_url=url.rstrip("/"), timeout=8) as client:
        health = await client.get("/api/health")
        health.raise_for_status()
        assert health.json()["status"] == "ok", "Backend unhealthy"
        response = await client.get("/api/simulation/status")
        response.raise_for_status()
        status = response.json()
        assert status["active_nodes"] == status["member_count"], "Some nodes are offline"
        assert len({n["pid"] for n in status["nodes"]}) == status["member_count"], "PIDs are not independent"
        page = await client.get("/")
        page.raise_for_status()
        assert 'lang="vi"' in page.text, "Vietnamese frontend was not served"
        assets = re.findall(r'(?:src|href)="(/assets/[^\"]+)"', page.text)
        assert assets, "Built frontend assets missing"
        for asset in assets:
            (await client.get(asset)).raise_for_status()
        ws_url = re.sub(r"^http", "ws", url.rstrip("/")) + "/ws/events"
        async with websockets.connect(ws_url, open_timeout=8) as ws:
            packet = json.loads(await asyncio.wait_for(ws.recv(), 8))
            assert packet["kind"] == "snapshot", "Unexpected WebSocket payload"
            assert len(packet["nodes"]) == status["member_count"]
        print(f"OK: HTTP, {status['member_count']} independent PIDs, frontend HTML/assets, live WebSocket.")
        print("Browser behavior still needs the checklist in docs/manual-testing.md.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    asyncio.run(check(args.url))
