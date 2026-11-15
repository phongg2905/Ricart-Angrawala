import pytest
from pydantic import ValidationError

from backend.app.core.algorithm import Algorithm, InvalidTransition
from backend.app.core.lamport_clock import LamportClock
from backend.app.core.models import ClusterConfig, ProtocolMessage, State


def message(kind="REQUEST", sender=2, receiver=1, request_id="remote", timestamp=6, request_timestamp=5):
    return ProtocolMessage(type=kind, session_id="test", sender_id=sender,
                           receiver_id=receiver, timestamp=timestamp, request_id=request_id,
                           request_timestamp=request_timestamp if kind == "REQUEST" else None)


def node(node_id=1):
    return Algorithm(node_id, {1, 2, 3}, "test")


def hold(a):
    a.request()
    for peer in sorted(a.peers):
        a.receive(message("REPLY", sender=peer, receiver=a.node_id, request_id=a.request_id))
    assert a.state == State.HELD


def test_initial_clock_and_local_ticks():
    clock = LamportClock()
    assert clock.value == 0
    assert clock.tick() == 1
    assert clock.tick() == 2


@pytest.mark.parametrize("local,remote,expected", [(0, 9, 10), (20, 4, 21), (5, 5, 6)])
def test_receive_clock(local, remote, expected):
    assert LamportClock(local).receive(remote) == expected


def test_request_clock_priority_and_send_increments():
    a = node()
    outgoing = a.request()
    assert a.priority == (1, 1)
    assert [m.timestamp for m in outgoing] == [2, 3]
    assert all(m.request_timestamp == 1 for m in outgoing)
    assert a.state == State.WANTED
    assert a.replies == set()
    a.receive(message("REPLY", request_id="stale", timestamp=80))
    assert a.clock.value == 81
    assert a.priority == (1, 1)


def test_released_immediate_reply_and_clock():
    a = node()
    reply, = a.receive(message())
    assert reply.type == "REPLY" and reply.request_id == "remote"
    assert reply.timestamp == 8  # receive 6 -> 7; send -> 8
    assert a.state == State.RELEASED


@pytest.mark.parametrize("node_id,sender,remote_ts,deferred", [
    (1, 2, 1, True), (2, 1, 1, False), (1, 2, 7, True),
])
def test_wanted_lexicographic_priority(node_id, sender, remote_ts, deferred):
    a = node(node_id)
    a.request()
    outgoing = a.receive(message(sender=sender, receiver=node_id,
                                 request_timestamp=remote_ts, timestamp=remote_ts + 1))
    assert bool(a.deferred) == deferred
    assert len(outgoing) == (0 if deferred else 1)


def test_wanted_remote_earlier_timestamp_has_priority():
    a = node()
    a.clock.value = 10
    a.request()
    assert a.receive(message())[0].type == "REPLY"


def test_held_defers_even_earlier_priority_and_release_flushes():
    a = node()
    hold(a)
    request_id = a.request_id
    assert a.receive(message()) == []
    assert len(a.deferred) == 1
    outgoing = a.release()
    assert [(m.receiver_id, m.request_id) for m in outgoing] == [(2, "remote")]
    assert a.state == State.RELEASED and a.completed == 1
    assert not a.deferred and a.request_id is None and not a.replies
    assert any(e["type"] == "CS_EXIT" and e["request_id"] == request_id for e in a.events)


def test_replies_must_be_unique_match_current_request_and_all_peers():
    a = node()
    a.request()
    a.receive(message("REPLY", request_id="old"))
    assert not a.replies
    reply = message("REPLY", request_id=a.request_id)
    a.receive(reply)
    a.receive(reply)
    assert a.replies == {2} and a.state == State.WANTED
    a.receive(message("REPLY", sender=3, request_id=a.request_id))
    assert a.state == State.HELD
    assert sum(e["type"] == "CS_ENTER" for e in a.events) == 1


def test_stale_reply_from_previous_round_cannot_grant_access():
    a = node()
    hold(a)
    old = a.request_id
    a.release()
    a.request()
    for peer in a.peers:
        a.receive(message("REPLY", sender=peer, request_id=old))
    assert a.state == State.WANTED and not a.replies


def test_duplicate_requests_do_not_duplicate_deferred_or_replies():
    a = node()
    outgoing = a.receive(message())
    assert len(outgoing) == 1 and a.receive(message()) == []
    hold(a)
    m = message(request_id="another")
    a.receive(m)
    a.receive(m)
    assert len(a.deferred) == 1


@pytest.mark.parametrize("state,action", [(State.RELEASED, "release"), (State.WANTED, "release"),
                                          (State.WANTED, "request"), (State.HELD, "request")])
def test_invalid_transitions(state, action):
    a = node()
    if state == State.WANTED:
        a.request()
    elif state == State.HELD:
        hold(a)
    with pytest.raises(InvalidTransition):
        getattr(a, action)()


@pytest.mark.parametrize("change", [{"session_id": "old"}, {"sender_id": 99}, {"receiver_id": 3}])
def test_membership_session_receiver_rejection(change):
    a = node()
    with pytest.raises(ValueError):
        a.receive(message().model_copy(update=change))
    assert a.clock.value == 0


@pytest.mark.parametrize("change", [{"request_timestamp": None}, {"request_timestamp": 7},
                                   {"timestamp": -1}, {"unexpected": True}])
def test_protocol_validation(change):
    with pytest.raises(ValidationError):
        ProtocolMessage.model_validate({**message().model_dump(), **change})


def test_membership_ids_are_unique():
    with pytest.raises(ValidationError):
        ClusterConfig(nodes=[{"id": 1, "port": 5001}, {"id": 1, "port": 5002}])


def test_exact_message_complexity_with_simultaneous_equal_priorities():
    nodes = {i: node(i) for i in (1, 2, 3)}
    queue = [m for a in nodes.values() for m in a.request()]
    entries = []
    delivered = []
    while queue or any(a.state != State.RELEASED for a in nodes.values()):
        while queue:
            m = queue.pop(0)
            delivered.append(m)
            queue.extend(nodes[m.receiver_id].receive(m))
        owners = [a for a in nodes.values() if a.state == State.HELD]
        assert len(owners) == 1
        entries.append(owners[0].node_id)
        queue.extend(owners[0].release())
    assert entries == [1, 2, 3]
    assert len(delivered) == 3 * 2 * (3 - 1)
