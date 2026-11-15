"""Process lifecycle and observation only. This module never grants CS permission."""
import asyncio
from collections import deque
from contextlib import suppress
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from ..core.models import ClusterConfig
from ..network.transport import rpc

ROOT = Path(__file__).resolve().parents[3]


class Simulation:
    def __init__(self, config_path: Path | None = None):
        self.config_path = config_path or Path(os.getenv("RA_CONFIG", str(ROOT / "config/nodes.example.json")))
        self.config = ClusterConfig.model_validate_json(self.config_path.read_text(encoding="utf-8"))
        self.processes: dict[int, subprocess.Popen] = {}
        self.log_files = []
        self.nodes: dict[int, dict] = {}
        self.cursors: dict[int, tuple[str, int]] = {}
        self.events: deque[dict] = deque(maxlen=6000)
        self.event_sequence = 0
        self.lifecycle = asyncio.Lock()
        self.refresh_lock = asyncio.Lock()
        self.poll_task: asyncio.Task | None = None
        self.running = False
        self.started = False
        self.error: str | None = None
        self.epoch = uuid4().hex
        self._offline_nodes()

    def _offline_nodes(self):
        self.nodes = {n.id: {"id": n.id, "state": "RELEASED", "clock": 0,
                           "host": n.host, "port": n.port,
                           "request_id": None, "request_timestamp": None, "replies": [],
                           "expected_replies": len(self.config.nodes) - 1, "deferred": [],
                           "completed": 0, "sent": {"REQUEST": 0, "REPLY": 0},
                           "online": False, "network_errors": {}, "connection_error": None}
                      for n in self.config.nodes}

    def add_event(self, event: dict) -> None:
        self.event_sequence += 1
        self.events.append({**event, "collection_id": self.event_sequence,
                            "collected_at": datetime.now(timezone.utc).isoformat()})

    async def command(self, node_id: int, action: str, **kwargs) -> dict:
        if self.error and action in ("REQUEST_CS", "RELEASE_CS"):
            raise ValueError(self.error)
        address = next((n for n in self.config.nodes if n.id == node_id), None)
        if not address:
            raise ValueError("Không có node này trong membership")
        response = await rpc(address.host, address.port,
                             {"type": "COMMAND", "action": action,
                              "session_id": self.config.session_id, **kwargs})
        if not response.get("ok"):
            raise ValueError(response.get("error", "Node từ chối lệnh"))
        return response

    async def poll_one(self, node_id: int) -> None:
        address = next(n for n in self.config.nodes if n.id == node_id)
        try:
            old_boot, cursor = self.cursors.get(node_id, ("", 0))
            response = await self.command(node_id, "STATUS", after=cursor)
            status = response["node"]
            if status["id"] != node_id or status["expected_replies"] != len(self.config.nodes) - 1:
                raise ValueError("Node trả về ID hoặc số thành viên khác cấu hình dashboard. Dùng cùng file và khởi động lại toàn phiên.")
            if old_boot and status["boot_id"] != old_boot:
                # An uncoordinated node restart violates the original failure assumptions.
                self.error = f"P{node_id} đã khởi động lại trong phiên. Dừng và reset toàn bộ membership."
                response = await self.command(node_id, "STATUS", after=0)
                status = response["node"]
                cursor = 0
            if status["oldest_seq"] > cursor + 1:
                self.add_event({"type": "OBSERVATION_GAP", "node_id": node_id,
                                "explanation": "Bộ đệm node đã xoay vòng; một phần lịch sử không còn khả dụng.",
                                "clock": status["clock"], "event_id": uuid4().hex})
            for event in status.pop("events"):
                self.add_event(event)
                cursor = event["seq"]
            self.cursors[node_id] = status["boot_id"], cursor
            self.nodes[node_id] = {**status, "online": True, "host": address.host,
                                   "port": address.port, "connection_error": None}
        except (OSError, TimeoutError, ValueError) as exc:
            if isinstance(exc, TimeoutError):
                reason = "Hết 2 giây chờ kết nối/phản hồi. Kiểm tra IP, node đang chạy và firewall."
            elif isinstance(exc, ConnectionRefusedError):
                reason = "Kết nối bị từ chối. Kiểm tra node đã mở đúng cổng."
            else:
                reason = str(exc) or type(exc).__name__
            self.nodes[node_id] = {**self.nodes[node_id], "online": False,
                                   "connection_error": f"{address.host}:{address.port} — {reason}"}

    async def refresh(self) -> None:
        async with self.refresh_lock:
            await asyncio.gather(*(self.poll_one(n.id) for n in self.config.nodes))

    async def poll(self) -> None:
        while True:
            if self.running or self.config.mode == "external":
                await self.refresh()
            await asyncio.sleep(0.2)

    async def open(self) -> None:
        logging.getLogger(__name__).info("Observer config=%s session=%s mode=%s members=%s",
                                        self.config_path.resolve(), self.config.session_id,
                                        self.config.mode, len(self.config.nodes))
        self.poll_task = asyncio.create_task(self.poll())

    async def start(self) -> dict:
        async with self.lifecycle:
            if self.started:
                return self.snapshot()
            if self.config.mode == "external":
                self.started = self.running = True
                await self.refresh()
                return self.snapshot()
            # Reject occupied ports instead of accidentally talking to an older cluster.
            for n in self.config.nodes:
                try:
                    reader, writer = await asyncio.wait_for(asyncio.open_connection(n.host, n.port), 0.4)
                except OSError:
                    continue
                except TimeoutError:
                    raise ValueError(f"Địa chỉ P{n.id} không phản hồi. Kiểm tra cấu hình local.")
                else:
                    writer.close()
                    await writer.wait_closed()
                    raise ValueError(f"Cổng {n.port} đã được dùng; hãy dừng tiến trình cũ trước.")
            self.config = self.config.model_copy(update={"session_id": uuid4().hex})
            runtime = ROOT / ".runtime"
            runtime.mkdir(exist_ok=True)
            runtime_config = runtime / "session.json"
            runtime_config.write_text(self.config.model_dump_json(indent=2), encoding="utf-8")
            self.events.clear()
            self.cursors.clear()
            self.epoch = uuid4().hex
            self._offline_nodes()
            self.error = None
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            try:
                for n in self.config.nodes:
                    output = (runtime / f"node-{n.id}.log").open("w", encoding="utf-8")
                    self.log_files.append(output)
                    self.processes[n.id] = subprocess.Popen(
                        [sys.executable, "-m", "backend.app.network.node", "--id", str(n.id),
                         "--config", str(runtime_config), "--audit-dir", str(runtime / "audit")],
                        cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, creationflags=flags,
                    )
                self.running = True
                # Windows antivirus can delay a new Python interpreter by >15s.
                # This is a readiness deadline, never a permission timeout.
                async with asyncio.timeout(45):
                    while True:
                        await self.refresh()
                        if all(n["online"] for n in self.nodes.values()):
                            break
                        if any(p.poll() is not None for p in self.processes.values()):
                            raise ValueError("Node khởi động lỗi; xem .runtime/node-*.log")
                        await asyncio.sleep(0.1)
                self.started = True
            except BaseException:
                await self._stop_local()
                raise
            return self.snapshot()

    async def _stop_local(self) -> None:
        self.running = self.started = False
        await asyncio.gather(*(self.command(i, "SHUTDOWN") for i in self.processes), return_exceptions=True)
        for proc in self.processes.values():
            try:
                await asyncio.wait_for(asyncio.to_thread(proc.wait), 4)
            except TimeoutError:
                proc.kill()
                await asyncio.to_thread(proc.wait)
        self.processes.clear()
        for output in self.log_files:
            output.close()
        self.log_files.clear()
        for status in self.nodes.values():
            status["online"] = False

    async def stop(self) -> dict:
        async with self.lifecycle:
            if self.config.mode == "external":
                raise ValueError("Node LAN được quản lý bên ngoài. Dừng trên từng máy; dashboard chỉ quan sát.")
            await self._stop_local()
            return self.snapshot()

    async def reset(self) -> dict:
        if self.config.mode == "external":
            raise ValueError("Reset LAN cần dừng và khởi động lại toàn bộ node với session_id mới.")
        await self.stop()
        return await self.start()

    async def close(self) -> None:
        if self.poll_task:
            self.poll_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.poll_task
        if self.config.mode == "local":
            await self._stop_local()

    def snapshot(self) -> dict:
        nodes = sorted(self.nodes.values(), key=lambda n: n["id"])
        online = sum(n["online"] for n in nodes)
        owners = [n["id"] for n in nodes if n["online"] and n["state"] == "HELD"]
        running = self.running or (self.config.mode == "external" and online > 0)
        return {"epoch": self.epoch, "session_id": self.config.session_id, "mode": self.config.mode,
                "config_path": str(self.config_path.resolve()), "running": running,
                "status": "DEGRADED" if running and online < len(nodes) else "RUNNING" if running else "STOPPED",
                "nodes": nodes, "active_nodes": online, "member_count": len(nodes),
                "owners": owners, "requests": sum(n["sent"]["REQUEST"] for n in nodes),
                "replies": sum(n["sent"]["REPLY"] for n in nodes),
                "completed": sum(n["completed"] for n in nodes),
                "safety": "UNCONFIRMED" if len(owners) > 1 or online < len(nodes) else "NO_VIOLATION_OBSERVED",
                "safety_note": "Snapshot thu thập bất đồng bộ; không phải bằng chứng an toàn. Kiểm thử dùng audit độc lập.",
                "error": self.error}
