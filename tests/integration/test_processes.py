import asyncio
import json

import pytest

from backend.app.network.transport import rpc
from tests.cluster import Cluster

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("count", [3, 4, 5])
async def test_single_request_actual_processes_and_complexity(tmp_path, count):
    async with Cluster(tmp_path, count) as c:
        initial = await c.statuses()
        assert len({s["pid"] for s in initial}) == count
        await c.command(1, "REQUEST_CS", duration=0.08)
        states = await c.until(lambda ss: sum(s["completed"] for s in ss) == 1)
        assert all(s["state"] == "RELEASED" for s in states)
        assert sum(s["sent"]["REQUEST"] for s in states) == count - 1
        assert sum(s["sent"]["REPLY"] for s in states) == count - 1
        c.assert_safety(1)


@pytest.mark.parametrize("count", [3, 4, 5])
async def test_all_competing_and_progress(tmp_path, count):
    async with Cluster(tmp_path, count) as c:
        await asyncio.gather(*(c.command(i, "REQUEST_CS", duration=0.06) for i in c.ports))
        states = await c.until(lambda ss: len(ss) == count and all(s["completed"] == 1 for s in ss))
        assert sum(s["sent"]["REQUEST"] + s["sent"]["REPLY"] for s in states) == count * 2 * (count - 1)
        c.assert_safety(count)


async def test_manual_release_deferred_and_no_permission_bypass(tmp_path):
    async with Cluster(tmp_path, 3) as c:
        await c.command(1, "REQUEST_CS", duration=None)
        await c.until(lambda ss: any(s["id"] == 1 and s["state"] == "HELD" for s in ss))
        await c.command(2, "REQUEST_CS", duration=0.06)
        states = await c.until(lambda ss: any(s["id"] == 1 and len(s["deferred"]) == 1 for s in ss))
        p2 = next(s for s in states if s["id"] == 2)
        assert p2["state"] == "WANTED" and 1 not in p2["replies"]
        await c.command(1, "RELEASE_CS")
        await c.until(lambda ss: sum(s["completed"] for s in ss) == 2)
        c.assert_safety(2)


async def test_missing_peer_blocks_and_warns(tmp_path):
    async with Cluster(tmp_path, 3) as c:
        await c.command(3, "SHUTDOWN")
        await asyncio.to_thread(c.processes[3].wait, 5)
        await c.command(1, "REQUEST_CS", duration=0.05)
        await c.until(lambda ss: any(s["id"] == 1 and s["network_errors"] for s in ss))
        # Bounded wait for the actual node-generated warning (8 seconds).
        states = await c.until(lambda ss: any(s["id"] == 1 and any(e["type"] == "WAIT_WARNING"
                                for e in s["events"]) for s in ss), timeout=12)
        p1 = next(s for s in states if s["id"] == 1)
        assert p1["state"] == "WANTED" and p1["completed"] == 0
        assert 3 not in p1["replies"]
        assert not any(e["type"] == "CS_ENTER" for e in c.audit())


async def test_framing_fragmentation_invalid_json_and_session(tmp_path):
    async with Cluster(tmp_path, 3) as c:
        reader, writer = await asyncio.open_connection("127.0.0.1", c.ports[1])
        payload = json.dumps({"type": "COMMAND", "action": "STATUS", "session_id": "integration"}).encode() + b"\n"
        writer.write(payload[:17])
        await writer.drain()
        writer.write(payload[17:])
        await writer.drain()
        assert json.loads(await reader.readline())["ok"]
        writer.close()
        await writer.wait_closed()
        for payload in [{"type": "BOGUS"}, {"type": "COMMAND", "action": "STATUS", "session_id": "old"}]:
            assert not (await rpc("127.0.0.1", c.ports[1], payload))["ok"]
        assert (await c.command(1))["clock"] == 0


async def test_shutdown_then_new_session_can_reuse_ports(tmp_path):
    c = Cluster(tmp_path / "first", 3)
    async with c:
        await c.command(1, "REQUEST_CS", duration=0.06)
        await c.until(lambda ss: sum(s["completed"] for s in ss) == 1)
    c2 = Cluster(tmp_path / "second", 3)
    c2.ports = c.ports
    c2.config["session_id"] = "new-session"
    c2.config["nodes"] = c.config["nodes"]
    c2.path.write_text(json.dumps(c2.config), encoding="utf-8")
    async with c2:
        assert all(s["clock"] == 0 for s in await c2.statuses())
        await c2.command(2, "REQUEST_CS", duration=0.06)
        await c2.until(lambda ss: sum(s["completed"] for s in ss) == 1)
        c2.assert_safety(1)


async def test_equal_timestamps_tie_break_over_real_tcp_with_delivery_barrier(tmp_path):
    """Proxies delay REQUEST delivery until all five nodes have created priorities.

    Commands connect to 127.0.0.1, protocol peers use 127.0.0.2 on the same ports.
    This is deterministic synchronization, not an assumption about scheduler speed.
    """
    c = Cluster(tmp_path, 5)
    for n in c.config["nodes"]:
        n["host"] = "127.0.0.2"
    c.path.write_text(json.dumps(c.config), encoding="utf-8")
    gate = asyncio.Event()
    servers = []
    tasks = set()

    def handler(port):
        async def forward(reader, writer):
            task = asyncio.current_task()
            tasks.add(task)
            try:
                data = json.loads(await reader.readline())
                if data["type"] == "REQUEST":
                    await gate.wait()
                response = await rpc("127.0.0.1", port, data)
                writer.write(json.dumps(response).encode() + b"\n")
                await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()
                tasks.discard(task)
        return forward

    try:
        for port in c.ports.values():
            servers.append(await asyncio.start_server(handler(port), "127.0.0.2", port))
        async with c:
            await asyncio.gather(*(c.command(i, "REQUEST_CS", duration=0.08) for i in c.ports))
            states = await c.statuses()
            assert {s["request_timestamp"] for s in states} == {1}
            assert all(s["state"] == "WANTED" and not s["replies"] for s in states)
            gate.set()
            await c.until(lambda ss: len(ss) == 5 and all(s["completed"] == 1 for s in ss))
            c.assert_safety(5)
            assert [e["node_id"] for e in c.audit() if e["type"] == "CS_ENTER"] == [1, 2, 3, 4, 5]
    finally:
        gate.set()
        for server in servers:
            server.close()
            await server.wait_closed()
        await asyncio.gather(*tasks, return_exceptions=True)


async def test_external_monitor_restart_does_not_control_permissions(tmp_path):
    from backend.app.services.simulation import Simulation
    async with Cluster(tmp_path, 3) as c:
        observer_config = tmp_path / "observer.json"
        observer_config.write_text(json.dumps({**c.config, "mode": "external"}), encoding="utf-8")
        observer = Simulation(observer_config)
        await observer.open()
        await observer.start()
        await observer.command(1, "REQUEST_CS", duration=0.1)
        await observer.close()  # External nodes must continue even without a monitor.
        await c.until(lambda ss: sum(s["completed"] for s in ss) == 1)
        restarted = Simulation(observer_config)
        await restarted.open()
        try:
            await restarted.start()
            assert restarted.snapshot()["completed"] == 1
            await restarted.command(2, "REQUEST_CS", duration=0.06)
            await c.until(lambda ss: sum(s["completed"] for s in ss) == 2)
        finally:
            await restarted.close()
        c.assert_safety(2)
