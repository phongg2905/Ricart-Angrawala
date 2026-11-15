"""Pure Ricart–Agrawala state machine; no sockets, timers, or central coordinator.

Callers serialize transitions. Returned messages are sent *after* the transition.
Every request keeps its original priority while message clocks continue to advance.
"""
from collections import deque
from typing import Any
from uuid import uuid4

from .lamport_clock import LamportClock
from .models import ProtocolMessage, State


class InvalidTransition(ValueError):
    pass


class Algorithm:
    def __init__(self, node_id: int, members: set[int], session_id: str):
        if node_id not in members or len(members) < 2:
            raise ValueError("Node must belong to a membership of at least two nodes")
        self.node_id = node_id
        self.peers = frozenset(members - {node_id})
        self.session_id = session_id
        self.clock = LamportClock()
        self.state = State.RELEASED
        self.request_id: str | None = None
        self.request_timestamp: int | None = None
        self.replies: set[int] = set()
        self.deferred: dict[tuple[int, str], ProtocolMessage] = {}
        self.seen_requests: set[tuple[int, str]] = set()
        self._seen_order: deque[tuple[int, str]] = deque()
        self.events: list[dict[str, Any]] = []
        self.completed = 0
        self.sent = {"REQUEST": 0, "REPLY": 0}

    @property
    def priority(self) -> tuple[int, int]:
        if self.request_timestamp is None:
            raise InvalidTransition("There is no active request")
        return self.request_timestamp, self.node_id

    def snapshot(self) -> dict[str, Any]:
        return {
            "id": self.node_id, "state": self.state.value, "clock": self.clock.value,
            "request_id": self.request_id, "request_timestamp": self.request_timestamp,
            "replies": sorted(self.replies), "expected_replies": len(self.peers),
            "deferred": [{"node_id": m.sender_id, "request_id": m.request_id}
                         for m in self.deferred.values()],
            "completed": self.completed, "sent": dict(self.sent),
        }

    def emit(self, kind: str, explanation: str, **extra: Any) -> None:
        self.events.append({"type": kind, "node_id": self.node_id,
                            "clock": self.clock.value, "request_id": self.request_id,
                            "explanation": explanation, **extra})

    def _send(self, kind: str, peer: int, request_id: str,
              request_timestamp: int | None = None) -> ProtocolMessage:
        message = ProtocolMessage(
            type=kind, session_id=self.session_id, sender_id=self.node_id,
            receiver_id=peer, timestamp=self.clock.tick(), request_id=request_id,
            request_timestamp=request_timestamp,
        )
        self.sent[kind] += 1
        self.emit("MESSAGE_SENT", f"Gửi {kind} đến P{peer}; đồng hồ tăng trước khi gửi.",
                  message=message.model_dump(exclude_none=True), request_id=request_id)
        return message

    def request(self) -> list[ProtocolMessage]:
        if self.state != State.RELEASED:
            raise InvalidTransition("Chỉ tiến trình RELEASED mới được yêu cầu vùng tới hạn")
        self.state = State.WANTED
        self.request_timestamp = self.clock.tick()
        self.request_id = uuid4().hex
        self.replies.clear()
        self.emit("REQUEST_CREATED", "Tạo yêu cầu; cặp ưu tiên được giữ cố định.",
                  priority=list(self.priority))
        return [self._send("REQUEST", p, self.request_id, self.request_timestamp)
                for p in sorted(self.peers)]

    def receive(self, message: ProtocolMessage) -> list[ProtocolMessage]:
        if (message.session_id != self.session_id or message.receiver_id != self.node_id
                or message.sender_id not in self.peers):
            raise ValueError("Message does not belong to this session/membership/receiver")
        before = self.clock.value
        self.clock.receive(message.timestamp)
        self.emit("MESSAGE_RECEIVED", "Nhận thông điệp: C = max(C, T) + 1.",
                  message=message.model_dump(exclude_none=True), previous_clock=before,
                  request_id=message.request_id)
        if message.type == "REPLY":
            if self.state != State.WANTED or message.request_id != self.request_id:
                self.emit("REPLY_IGNORED", "Bỏ qua REPLY cũ hoặc không có yêu cầu tương ứng.",
                          request_id=message.request_id)
            elif message.sender_id in self.replies:
                self.emit("REPLY_IGNORED", "REPLY trùng không được tính thêm.")
            else:
                self.replies.add(message.sender_id)
                if self.replies == self.peers:
                    self.clock.tick()
                    self.state = State.HELD
                    self.emit("CS_ENTER", "Đã nhận đủ N − 1 REPLY hợp lệ; vào vùng tới hạn.")
            return []

        key = (message.sender_id, message.request_id)
        if key in self.seen_requests:
            self.emit("REQUEST_IGNORED", "Bỏ qua REQUEST trùng; không gửi thêm quyền.",
                      request_id=message.request_id)
            return []
        self.seen_requests.add(key)
        self._seen_order.append(key)
        # Bound duplicate history; eviction never changes active deferred permissions.
        if len(self._seen_order) > 10000:
            old = self._seen_order.popleft()
            self.seen_requests.discard(old)
        defer = self.state == State.HELD or (
            self.state == State.WANTED
            and self.priority < (message.request_timestamp, message.sender_id)
        )
        if defer:
            self.deferred[key] = message
            self.emit("REPLY_DEFERRED", f"Hoãn REPLY cho P{message.sender_id}: đang HELD hoặc có ưu tiên trước.",
                      peer_id=message.sender_id, request_id=message.request_id)
            return []
        return [self._send("REPLY", message.sender_id, message.request_id)]

    def release(self) -> list[ProtocolMessage]:
        if self.state != State.HELD:
            raise InvalidTransition("Chỉ tiến trình HELD mới được giải phóng vùng tới hạn")
        self.clock.tick()
        self.state = State.RELEASED
        self.completed += 1
        self.emit("CS_EXIT", "Rời vùng tới hạn; giải phóng các REPLY đã hoãn.")
        pending = sorted(self.deferred.values(),
                         key=lambda m: (m.request_timestamp, m.sender_id))
        self.deferred.clear()
        self.request_id = None
        self.request_timestamp = None
        self.replies.clear()
        return [self._send("REPLY", m.sender_id, m.request_id) for m in pending]
