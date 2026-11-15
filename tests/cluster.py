"""Real child processes and TCP. Bounded condition polling, independent per-node audits."""
import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

from backend.app.network.transport import rpc

ROOT = Path(__file__).resolve().parents[1]


def free_ports(count):
    sockets = []
    try:
        for _ in range(count):
            s = socket.socket()
            s.bind(("127.0.0.1", 0))
            sockets.append(s)
        return [s.getsockname()[1] for s in sockets]
    finally:
        for s in sockets:
            s.close()


class Cluster:
    def __init__(self, tmp_path, count=5):
        self.directory = tmp_path
        self.directory.mkdir(parents=True, exist_ok=True)
        self.ports = dict(zip(range(1, count + 1), free_ports(count)))
        self.config = {"session_id": "integration", "mode": "local", "nodes": [
            {"id": i, "host": "127.0.0.1", "bind_host": "127.0.0.1", "port": p}
            for i, p in self.ports.items()]}
        self.path = tmp_path / "cluster.json"
        self.path.write_text(json.dumps(self.config), encoding="utf-8")
        self.processes = {}
        self.logs = []

    async def __aenter__(self):
        try:
            for i in self.ports:
                output = (self.directory / f"process-{i}.log").open("w", encoding="utf-8")
                self.logs.append(output)
                self.processes[i] = subprocess.Popen(
                    [sys.executable, "-m", "backend.app.network.node", "--id", str(i),
                     "--config", str(self.path), "--audit-dir", str(self.directory / "audit")],
                    cwd=ROOT, stdout=output, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            await self.until(lambda s: len(s) == len(self.ports), timeout=45)
            return self
        except BaseException:
            await self.__aexit__(None, None, None)
            raise

    async def command(self, i, action="STATUS", **kwargs):
        response = await rpc("127.0.0.1", self.ports[i],
                             {"type": "COMMAND", "session_id": self.config["session_id"],
                              "action": action, **kwargs})
        assert response.get("ok"), response
        return response.get("node", {})

    async def statuses(self):
        responses = await asyncio.gather(*(self.command(i) for i in self.ports), return_exceptions=True)
        return [s for s in responses if isinstance(s, dict)]

    async def until(self, predicate, timeout=12):
        async with asyncio.timeout(timeout):
            while True:
                statuses = await self.statuses()
                if predicate(statuses):
                    return statuses
                await asyncio.sleep(0.02)

    def audit(self):
        records = []
        for path in (self.directory / "audit").glob("*.jsonl"):
            records.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())
        return sorted(records, key=lambda e: e["monotonic_ns"])

    def assert_safety(self, expected):
        owners = set()
        entries = []
        records = self.audit()
        for event in records:
            if event["type"] == "CS_ENTER":
                assert not owners, f"Overlapping CS: {owners} and P{event['node_id']}"
                owners.add(event["node_id"])
                entries.append(event)
            elif event["type"] == "CS_EXIT":
                assert event["node_id"] in owners
                owners.remove(event["node_id"])
        assert not owners
        assert len(entries) == expected
        # Every entry needs exactly one valid permission from EACH other process.
        for entry in entries:
            replies = {e["message"]["sender_id"] for e in records
                       if e["type"] == "MESSAGE_RECEIVED" and e["node_id"] == entry["node_id"]
                       and e["request_id"] == entry["request_id"] and e["message"]["type"] == "REPLY"
                       and e["seq"] < entry["seq"]}
            assert replies == set(self.ports) - {entry["node_id"]}

    async def __aexit__(self, *args):
        await asyncio.gather(*(self.command(i, "SHUTDOWN") for i in self.processes), return_exceptions=True)
        for proc in self.processes.values():
            try:
                await asyncio.wait_for(asyncio.to_thread(proc.wait), 4)
            except TimeoutError:
                proc.kill()
                await asyncio.to_thread(proc.wait)
        for output in self.logs:
            output.close()
