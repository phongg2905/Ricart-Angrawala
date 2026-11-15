import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .services.simulation import ROOT, Simulation


class RequestOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    duration: float | None = Field(default=3.0, ge=0.05, le=120)


def create_app(config_path: Path | None = None) -> FastAPI:
    simulation = Simulation(config_path)

    @asynccontextmanager
    async def lifespan(app):
        await simulation.open()
        try:
            yield
        finally:
            await simulation.close()

    app = FastAPI(title="Ricart & Agrawala Simulator", version="1.0.0", lifespan=lifespan)
    app.state.simulation = simulation

    async def invoke(operation):
        try:
            return await operation
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        except (OSError, TimeoutError) as exc:
            raise HTTPException(503, f"Không kết nối được node: {exc}") from exc

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "role": "observer-and-command-relay"}

    @app.get("/api/nodes")
    async def nodes():
        return simulation.snapshot()["nodes"]

    @app.get("/api/simulation/status")
    async def status():
        return simulation.snapshot()

    @app.get("/api/simulation/events")
    async def events(after: int = 0, limit: int = 200):
        if after < 0 or not 1 <= limit <= 1000:
            raise HTTPException(422, "after >= 0; limit từ 1 đến 1000")
        return {"epoch": simulation.epoch,
                "events": [e for e in simulation.events if e["collection_id"] > after][:limit]}

    @app.post("/api/simulation/start")
    async def start():
        return await invoke(simulation.start())

    @app.post("/api/simulation/stop")
    async def stop():
        return await invoke(simulation.stop())

    @app.post("/api/simulation/reset")
    async def reset():
        return await invoke(simulation.reset())

    @app.post("/api/nodes/{node_id}/request")
    async def request(node_id: int, options: RequestOptions):
        return await invoke(simulation.command(node_id, "REQUEST_CS", duration=options.duration))

    @app.post("/api/nodes/{node_id}/release")
    async def release(node_id: int):
        return await invoke(simulation.command(node_id, "RELEASE_CS"))

    @app.websocket("/ws/events")
    async def websocket(ws: WebSocket):
        await ws.accept()
        cursor = 0
        epoch = ""
        try:
            while True:
                if epoch != simulation.epoch:
                    epoch, cursor = simulation.epoch, 0
                batch = [e for e in simulation.events if e["collection_id"] > cursor][-300:]
                await ws.send_json({"kind": "snapshot", **simulation.snapshot(), "events": batch})
                if batch:
                    cursor = batch[-1]["collection_id"]
                await asyncio.sleep(0.2)
        except (WebSocketDisconnect, OSError, RuntimeError):
            pass

    dist = ROOT / "frontend/dist"
    if dist.exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/")
        async def index():
            return FileResponse(dist / "index.html")

    return app


app = create_app()
