from fastapi.testclient import TestClient
import pytest

from backend.app.main import create_app
from tests.cluster import Cluster

pytestmark = pytest.mark.integration


def test_management_api_websocket_and_safe_reset(tmp_path):
    config = Cluster(tmp_path, 5).path
    app = create_app(config)
    with TestClient(app) as client:
        assert client.get("/api/health").json()["role"] == "observer-and-command-relay"
        assert client.get("/api/nodes").status_code == 200
        assert client.post("/api/nodes/99/request", json={"duration": 1}).status_code == 409
        assert client.post("/api/nodes/1/request", json={"duration": -1}).status_code == 422
        assert client.post("/api/simulation/start").status_code == 200
        start = client.get("/api/simulation/status").json()
        assert start["active_nodes"] == 5
        assert len({n["pid"] for n in start["nodes"]}) == 5
        assert client.post("/api/nodes/1/release").status_code == 409
        assert client.post("/api/nodes/1/request", json={"duration": None}).status_code == 200
        # Receive actual streamed node events instead of arbitrary sleep.
        with client.websocket_connect("/ws/events") as ws:
            for _ in range(100):
                packet = ws.receive_json()
                if any(n["id"] == 1 and n["state"] == "HELD" for n in packet["nodes"]):
                    break
            else:
                pytest.fail("P1 never reached HELD")
            assert any(e["type"] == "CS_ENTER" for e in
                       client.get("/api/simulation/events?limit=1000").json()["events"])
        assert client.post("/api/nodes/1/request", json={"duration": 1}).status_code == 409
        assert client.post("/api/nodes/1/release").status_code == 200
        assert client.get("/api/simulation/events?limit=0").status_code == 422
        assert client.post("/api/simulation/reset").status_code == 200
        reset = client.get("/api/simulation/status").json()
        assert reset["session_id"] != start["session_id"]
        assert all(n["clock"] == 0 for n in reset["nodes"])
        assert client.post("/api/simulation/stop").json()["status"] == "STOPPED"
    assert not app.state.simulation.processes
