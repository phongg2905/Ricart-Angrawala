import json

import pytest

from backend.app.core.algorithm import Algorithm
from backend.app.services.simulation import Simulation


def observer(tmp_path):
    path = tmp_path / "four.json"
    path.write_text(json.dumps({"session_id": "diagnostics", "mode": "external", "nodes": [
        {"id": i, "host": "127.0.0.1", "port": 5000 + i} for i in range(1, 5)]}), encoding="utf-8")
    return Simulation(path)


def status(node_id=1, members=None):
    return {**Algorithm(node_id, members or {1, 2, 3, 4}, "diagnostics").snapshot(),
            "boot_id": "boot", "session_id": "diagnostics", "events": [],
            "last_seq": 0, "oldest_seq": 0}


def test_external_partial_membership_is_degraded_without_start_command(tmp_path):
    s = observer(tmp_path)
    s.nodes[1]["online"] = True
    snapshot = s.snapshot()
    assert snapshot["running"] and snapshot["status"] == "DEGRADED"
    assert snapshot["active_nodes"] == 1 and snapshot["member_count"] == 4
    assert snapshot["config_path"].endswith("four.json")


async def test_timeout_explains_node_endpoint_instead_of_empty_error(tmp_path, monkeypatch):
    s = observer(tmp_path)

    async def timeout(*args, **kwargs):
        raise TimeoutError()

    monkeypatch.setattr("backend.app.services.simulation.rpc", timeout)
    await s.poll_one(1)
    assert not s.nodes[1]["online"]
    assert "127.0.0.1:5001" in s.nodes[1]["connection_error"]
    assert "2 giây" in s.nodes[1]["connection_error"]


async def test_reconnected_node_clears_error_and_keeps_address(tmp_path, monkeypatch):
    s = observer(tmp_path)
    s.nodes[1]["connection_error"] = "previous connection failed"

    async def online(*args, **kwargs):
        return {"ok": True, "node": status()}

    monkeypatch.setattr("backend.app.services.simulation.rpc", online)
    await s.poll_one(1)
    assert s.nodes[1]["online"]
    assert s.nodes[1]["connection_error"] is None
    assert (s.nodes[1]["host"], s.nodes[1]["port"]) == ("127.0.0.1", 5001)


@pytest.mark.parametrize("reported", [status(2), status(1, {1, 2, 3})])
async def test_wrong_node_or_membership_is_not_reported_online(tmp_path, monkeypatch, reported):
    s = observer(tmp_path)

    async def wrong_config(*args, **kwargs):
        return {"ok": True, "node": reported}

    monkeypatch.setattr("backend.app.services.simulation.rpc", wrong_config)
    await s.poll_one(1)
    assert not s.nodes[1]["online"]
    assert "cấu hình" in s.nodes[1]["connection_error"]
