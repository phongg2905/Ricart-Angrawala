"""Validated wire contracts. Protocol traffic and management commands are separate."""
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class State(StrEnum):
    RELEASED = "RELEASED"
    WANTED = "WANTED"
    HELD = "HELD"


class ProtocolMessage(StrictModel):
    type: Literal["REQUEST", "REPLY"]
    session_id: str = Field(min_length=1, max_length=128)
    sender_id: int = Field(gt=0)
    receiver_id: int = Field(gt=0)
    timestamp: int = Field(ge=1)
    request_id: str = Field(min_length=1, max_length=128)
    request_timestamp: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def valid_request(self):
        if self.type == "REQUEST":
            if self.request_timestamp is None or self.request_timestamp >= self.timestamp:
                raise ValueError("REQUEST needs a request_timestamp preceding its send timestamp")
        elif self.request_timestamp is not None:
            raise ValueError("REPLY must not contain a request_timestamp")
        return self


class Command(StrictModel):
    type: Literal["COMMAND"] = "COMMAND"
    action: Literal["STATUS", "REQUEST_CS", "RELEASE_CS", "SHUTDOWN"]
    session_id: str
    after: int = Field(default=0, ge=0)
    duration: float | None = Field(default=3.0, ge=0.05, le=120)


class NodeAddress(StrictModel):
    id: int = Field(gt=0)
    host: str = "127.0.0.1"
    bind_host: str = "127.0.0.1"
    port: int = Field(ge=1024, le=65535)


class ClusterConfig(StrictModel):
    session_id: str = Field(default="lan-demo-001", min_length=1, max_length=128)
    mode: Literal["local", "external"] = "local"
    monitoring_backend: str = "http://127.0.0.1:8000"
    nodes: list[NodeAddress] = Field(min_length=2, max_length=10)

    @model_validator(mode="after")
    def unique_members(self):
        if len({n.id for n in self.nodes}) != len(self.nodes):
            raise ValueError("Node IDs must be unique")
        if len({(n.host, n.port) for n in self.nodes}) != len(self.nodes):
            raise ValueError("Advertised addresses must be unique")
        return self
