"""Independent OS node. Management/monitor disconnection does not stop the algorithm."""
import argparse
import asyncio
from collections import deque
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import signal
import time
from uuid import uuid4

from ..core.algorithm import Algorithm, InvalidTransition
from ..core.models import ClusterConfig, Command, ProtocolMessage, State
from .transport import MAX_FRAME, rpc

log = logging.getLogger(__name__)


class Node:
    def __init__(self, config: ClusterConfig, node_id: int, audit_dir: Path | None = None):
        self.config = config
        self.address = next(n for n in config.nodes if n.id == node_id)
        self.peers = {n.id: n for n in config.nodes if n.id != node_id}
        self.algorithm = Algorithm(node_id, {n.id for n in config.nodes}, config.session_id)
        self.lock = asyncio.Lock()
        self.outbox: asyncio.Queue[ProtocolMessage] = asyncio.Queue()
        self.events: deque[dict] = deque(maxlen=4000)
        self.sequence = 0
        self.boot_id = uuid4().hex
        self.stopping = asyncio.Event()
        self.duration: float | None = 3.0
        self.timer: asyncio.Task | None = None
        self.wait_warning: asyncio.Task | None = None
        self.connections: set[asyncio.Task] = set()
        self.errors: dict[int, str] = {}
        self.audit = None
        if audit_dir:
            audit_dir.mkdir(parents=True, exist_ok=True)
            self.audit = (audit_dir / f"node-{node_id}.jsonl").open("a", encoding="utf-8", buffering=1)

    def record(self, event: dict) -> None:
        self.sequence += 1
        event.update(seq=self.sequence, event_id=f"{self.boot_id}:{self.sequence}",
                     boot_id=self.boot_id, session_id=self.config.session_id,
                     observed_at=datetime.now(timezone.utc).isoformat(),
                     # QPC on Windows: monotonic_ns() in Python 3.11 is too coarse
                     # to distinguish adjacent protocol events (often 15.6 ms).
                     monotonic_ns=time.perf_counter_ns())
        self.events.append(event)
        if self.audit:
            self.audit.write(json.dumps(event, ensure_ascii=False) + "\n")

    def flush(self, outgoing: list[ProtocolMessage]) -> None:
        for event in self.algorithm.events:
            self.record(event)
            if event["type"] == "CS_ENTER":
                if self.wait_warning:
                    self.wait_warning.cancel()
                if self.duration is not None:
                    self.timer = asyncio.create_task(self.auto_release(self.algorithm.request_id, self.duration))
        self.algorithm.events.clear()
        for message in outgoing:
            self.outbox.put_nowait(message)

    def status(self, after: int) -> dict:
        events = [e for e in self.events if e["seq"] > after][:200]
        return {**self.algorithm.snapshot(), "pid": __import__("os").getpid(),
                "boot_id": self.boot_id, "session_id": self.config.session_id,
                "events": events, "last_seq": self.sequence,
                "oldest_seq": self.events[0]["seq"] if self.events else 0,
                "network_errors": dict(self.errors), "duration": self.duration}

    async def auto_release(self, request_id: str, duration: float) -> None:
        await asyncio.sleep(duration)
        async with self.lock:
            if self.algorithm.state == State.HELD and self.algorithm.request_id == request_id:
                self.flush(self.algorithm.release())

    async def warn_wait(self, request_id: str) -> None:
        await asyncio.sleep(8)
        async with self.lock:
            if self.algorithm.state == State.WANTED and self.algorithm.request_id == request_id:
                self.record({"node_id": self.address.id, "type": "WAIT_WARNING",
                             "clock": self.algorithm.clock.value, "request_id": request_id,
                             "explanation": "Chờ quá 8 giây. Không bỏ qua quyền còn thiếu; kiểm tra peer hoặc tiến trình HELD."})

    async def dispatch(self, data: dict) -> dict:
        async with self.lock:
            if data.get("type") in ("REQUEST", "REPLY"):
                message = ProtocolMessage.model_validate(data)
                self.flush(self.algorithm.receive(message))
                return {"ok": True}  # transport ACK is never an algorithm REPLY
            command = Command.model_validate(data)
            if command.session_id != self.config.session_id:
                raise ValueError("Session mismatch; coordinated restart required")
            if command.action == "STATUS":
                return {"ok": True, "node": self.status(command.after)}
            if command.action == "REQUEST_CS":
                outgoing = self.algorithm.request()
                self.duration = command.duration
                self.flush(outgoing)
                self.wait_warning = asyncio.create_task(self.warn_wait(self.algorithm.request_id))
            elif command.action == "RELEASE_CS":
                self.flush(self.algorithm.release())
                if self.timer:
                    self.timer.cancel()
            elif command.action == "SHUTDOWN":
                # A failed/missing node never transfers its permission to another node.
                self.stopping.set()
            return {"ok": True, "node": self.status(self.sequence)}

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        self.connections.add(task)
        try:
            async with asyncio.timeout(4):
                frame = await reader.readline()
                if not frame.endswith(b"\n"):
                    raise ValueError("Expected newline-delimited JSON")
                data = json.loads(frame)
                if not isinstance(data, dict):
                    raise ValueError("Expected an object")
                response = await self.dispatch(data)
        except (ValueError, TimeoutError, InvalidTransition) as exc:
            response = {"ok": False, "error": str(exc)}
        except (ConnectionError, OSError, asyncio.CancelledError):
            self.connections.discard(task)
            writer.close()
            return
        try:
            writer.write(json.dumps(response, ensure_ascii=False).encode() + b"\n")
            await writer.drain()
        except (ConnectionError, OSError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, OSError, asyncio.CancelledError):
                pass
            self.connections.discard(task)

    async def send_loop(self) -> None:
        while True:
            message = await self.outbox.get()
            peer = self.peers[message.receiver_id]
            try:
                response = await rpc(peer.host, peer.port, message.model_dump(exclude_none=True))
                if not response.get("ok"):
                    raise ConnectionError(response.get("error", "Peer rejected message"))
                self.errors.pop(peer.id, None)
            except (OSError, TimeoutError, ValueError) as exc:
                self.errors[peer.id] = str(exc)
                self.record({"node_id": self.address.id, "type": "NETWORK_ERROR",
                             "clock": self.algorithm.clock.value, "request_id": message.request_id,
                             "explanation": f"Không gửi được {message.type} đến P{peer.id}: {exc}. Không tự cấp quyền.",
                             "peer_id": peer.id})
            finally:
                self.outbox.task_done()

    async def run(self) -> None:
        server = await asyncio.start_server(self.handle, self.address.bind_host,
                                            self.address.port, limit=MAX_FRAME)
        self.record({"type": "NODE_STARTED", "node_id": self.address.id, "clock": 0,
                     "explanation": "Tiến trình TCP độc lập đã sẵn sàng."})
        sender = asyncio.create_task(self.send_loop())
        log.info("P%s listening on %s:%s", self.address.id, self.address.bind_host, self.address.port)
        try:
            async with server:
                await self.stopping.wait()
        finally:
            server.close()
            await server.wait_closed()
            tasks = [sender, self.timer, self.wait_warning, *self.connections]
            for task in tasks:
                if task:
                    task.cancel()
            await asyncio.gather(*(t for t in tasks if t), return_exceptions=True)
            if self.audit:
                self.audit.close()


async def main_async(args) -> None:
    config = ClusterConfig.model_validate_json(Path(args.config).read_text(encoding="utf-8"))
    node = Node(config, args.id, Path(args.audit_dir) if args.audit_dir else None)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, node.stopping.set)
        except NotImplementedError:
            pass  # Windows is stopped through the management command or parent process.
    await node.run()


def main() -> None:
    parser = argparse.ArgumentParser(description="Independent Ricart–Agrawala TCP node")
    parser.add_argument("--id", type=int, required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--audit-dir")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
