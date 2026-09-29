"""Protocol security tests. Any simulated dispatch is explicitly labelled."""

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from cascadeur_mcp.bridge import host
from cascadeur_mcp.bridge.client import BridgeClient
from cascadeur_mcp.bridge.protocol import (BridgeError, MAX_BYTES, read_json,
                                          validate_params, write_json)


@pytest.mark.parametrize("method,params", [
    ("execute_python", {}), ("ping_cascadeur", {"code": "anything"}),
    ("get_scene_info", []), ("get_objects", {"limit": True}),
    ("get_objects", {"limit": 201}), ("get_objects", {"limit": 0}),
    ("get_objects", {"offset": -1}), ("get_objects", {"offset": "1"}),
    ("get_objects", {"path": "../outside"}),
])
def test_reject_invalid_input(method, params):
    with pytest.raises(BridgeError):
        validate_params(method, params)


def test_missing_bridge_is_not_a_pong(tmp_path):
    with pytest.raises(BridgeError, match="BRIDGE_UNAVAILABLE"):
        BridgeClient(tmp_path).call("ping_cascadeur")


def test_client_claim_during_response_cleanup_does_not_stop_host(tmp_path, monkeypatch):
    from pathlib import Path
    bridge=host.HostBridge(tmp_path)
    response=bridge.folder/('a'*32+'.response.json')
    response.write_text('{}')
    native_stat=Path.stat
    def claimed_stat(path,*args,**kwargs):
        if path==response:
            response.unlink()
            raise FileNotFoundError(str(path))
        return native_stat(path,*args,**kwargs)
    monkeypatch.setattr(Path,'stat',claimed_stat)
    bridge.tick()
    assert not hasattr(bridge,'last_transport_error')


def test_timeout_removes_request(tmp_path):
    bridge = host.HostBridge(tmp_path)
    bridge.publish()
    with pytest.raises(BridgeError, match="BRIDGE_TIMEOUT"):
        BridgeClient(tmp_path, timeout=0.1).call("ping_cascadeur")
    assert not list(bridge.folder.glob("*.request.json"))


def test_existing_descriptor_is_not_overwritten(tmp_path):
    first = host.HostBridge(tmp_path)
    first.publish()
    second = host.HostBridge(tmp_path)
    with pytest.raises(BridgeError, match="SESSION_EXISTS"):
        second.publish()
    assert read_json(tmp_path / "session.json")["session"] == first.session


def test_atomic_json_and_size_limits(tmp_path):
    path = tmp_path / "message.json"
    write_json(path, {"name": "中文"})
    assert read_json(path) == {"name": "中文"}
    with pytest.raises(BridgeError, match="MESSAGE_TOO_LARGE"):
        write_json(path, {"data": "x" * MAX_BYTES})
    assert not list(tmp_path.glob("*.tmp"))
    path.write_bytes(b"x" * (MAX_BYTES + 1))
    with pytest.raises(BridgeError, match="MESSAGE_TOO_LARGE"):
        read_json(path)


def request_for(bridge, **changes):
    rid = uuid.uuid4().hex
    data = {"version": 1, "id": rid, "session": bridge.session, "token": bridge.token,
            "expires_at": time.time() + 5, "method": "ping_cascadeur", "params": {}}
    data.update(changes)
    return rid, data


@pytest.mark.parametrize("changes,reason", [
    ({"token": "wrong"}, "UNAUTHORIZED"),
    ({"session": "wrong"}, "UNAUTHORIZED"),
    ({"expires_at": 0}, "EXPIRED_REQUEST"),
    ({"expires_at": "soon"}, "INVALID_EXPIRY"),
    ({"method": "execute_python"}, "UNKNOWN_METHOD"),
    ({"params": {"code": "print(1)"}}, "INVALID_PARAMS"),
    ({"version": True}, "INVALID_VERSION"),
])
def test_rejected_requests_never_dispatch(tmp_path, monkeypatch, changes, reason):
    bridge = host.HostBridge(tmp_path)
    calls = []
    monkeypatch.setattr(host, "dispatch", lambda *args: calls.append(args))
    rid, data = request_for(bridge, **changes)
    write_json(bridge.folder / (rid + ".request.json"), data)
    bridge.tick()
    response = read_json(bridge.folder / (rid + ".response.json"))
    assert response["ok"] is False and reason in response["error"]
    assert calls == []


def test_roundtrip_with_explicit_fake_dispatch(tmp_path, monkeypatch):
    bridge = host.HostBridge(tmp_path)
    bridge.publish()
    calls = []

    def fake_dispatch(method, params):
        calls.append(threading.get_ident())
        return {"fixture": "SIMULATED_TRANSPORT_ONLY", "method": method}

    monkeypatch.setattr(host, "dispatch", fake_dispatch)
    with ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(BridgeClient(tmp_path).call, "ping_cascadeur")
        deadline = time.monotonic() + 3
        while not result.done() and time.monotonic() < deadline:
            bridge.tick()
            time.sleep(0.01)
        assert result.result()["fixture"] == "SIMULATED_TRANSPORT_ONLY"
    assert calls == [threading.get_ident()]


def test_replay_is_rejected(tmp_path, monkeypatch):
    bridge = host.HostBridge(tmp_path)
    calls = []
    def fake_dispatch(*args):
        calls.append(args)
        return {"fixture": "SIMULATED"}
    monkeypatch.setattr(host, "dispatch", fake_dispatch)
    rid, data = request_for(bridge)
    for _ in range(2):
        write_json(bridge.folder / (rid + ".request.json"), data)
        bridge.tick()
    result = read_json(bridge.folder / (rid + ".response.json"))
    assert "DUPLICATE_REQUEST" in result["error"]
    assert len(calls) == 1


def test_wrong_thread_is_rejected(tmp_path):
    bridge = host.HostBridge(tmp_path)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with pytest.raises(BridgeError, match="WRONG_THREAD"):
            pool.submit(bridge._tick).result()
