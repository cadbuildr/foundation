"""Unit tests for KernelApiClient's unix-socket sidecar transport.

A fake NDJSON sidecar runs on a real unix socket in a background thread;
no HTTP and no actual kernel involved.
"""

from __future__ import annotations

import base64
import json
import socket
import threading
import uuid
from pathlib import Path

import pytest

from cadbuildr.foundation.coms.kernel_api import KernelApiClient, KernelApiError

FAKE_STL = b"\x00" * 84 + b"fake-triangles"


class FakeSidecar:
    """Minimal NDJSON-over-unix-socket server mimicking kernelSidecar.js."""

    def __init__(self, socket_path: str, reply_builder) -> None:
        self.socket_path = socket_path
        self.requests: list[dict] = []
        self._reply_builder = reply_builder
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(socket_path)
        self._server.listen(4)
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        while True:
            try:
                conn, _ = self._server.accept()
            except OSError:
                return
            with conn:
                buf = b""
                while b"\n" not in buf:
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    buf += chunk
                if b"\n" not in buf:
                    continue
                request = json.loads(buf.split(b"\n", 1)[0])
                self.requests.append(request)
                reply = self._reply_builder(request)
                conn.sendall((json.dumps(reply) + "\n").encode())

    def close(self) -> None:
        self._server.close()


@pytest.fixture()
def socket_path(tmp_path: Path) -> str:
    # Unix socket paths are length-limited (~104 bytes on macOS): tmp_path
    # can exceed that, so anchor in /tmp with a unique suffix instead.
    return f"/tmp/cadbuildr-test-{uuid.uuid4().hex[:12]}.sock"


def _ok_reply(request: dict) -> dict:
    if request.get("op") == "ping":
        return {"id": request.get("id"), "ok": True, "pong": True}
    return {
        "id": request.get("id"),
        "ok": True,
        "format": request.get("format", "stl"),
        "stl_base64": base64.b64encode(FAKE_STL).decode(),
        "mesh": {"root": {"name": "part"}},
        "assemblyWarnings": [{"type": "isolated_part", "name": "ghost"}],
    }


def test_download_stl_over_socket_decodes_bytes_and_captures_warnings(socket_path):
    sidecar = FakeSidecar(socket_path, _ok_reply)
    try:
        client = KernelApiClient(socket_path=socket_path)
        stl = client.download_stl(dag={"rootNodeId": "0", "DAG": {}}, kernel="replicad")
        assert stl == FAKE_STL
        assert client.last_assembly_warnings == [{"type": "isolated_part", "name": "ghost"}]
        assert sidecar.requests[0]["format"] == "stl"
        assert sidecar.requests[0]["dag"] == {"rootNodeId": "0", "DAG": {}}
    finally:
        sidecar.close()


def test_socket_env_var_activates_transport(socket_path, monkeypatch):
    monkeypatch.setenv("CADBUILDR_KERNEL_SOCKET", socket_path)
    sidecar = FakeSidecar(socket_path, _ok_reply)
    try:
        client = KernelApiClient()
        assert client.socket_path == socket_path
        mesh = client.compile_mesh(dag={"rootNodeId": "0"})
        assert mesh["format"] == "json"
        assert mesh["mesh"] == {"root": {"name": "part"}}
        assert mesh["assemblyWarnings"] == [{"type": "isolated_part", "name": "ghost"}]
    finally:
        sidecar.close()


def test_socket_error_reply_raises_kernel_api_error(socket_path):
    def _error_reply(request: dict) -> dict:
        return {
            "id": request.get("id"),
            "ok": False,
            "error": {"code": "kernel_error", "message": "Replicad kernel error: bad sweep"},
        }

    sidecar = FakeSidecar(socket_path, _error_reply)
    try:
        client = KernelApiClient(socket_path=socket_path)
        with pytest.raises(KernelApiError, match="bad sweep") as exc_info:
            client.download_stl(dag={"rootNodeId": "0"})
        assert exc_info.value.code == "kernel_error"
    finally:
        sidecar.close()


def test_socket_rejects_step_and_truck(socket_path):
    client = KernelApiClient(socket_path=socket_path)
    with pytest.raises(KernelApiError, match="does not support format 'step'"):
        client.render(dag={}, format="step")
    with pytest.raises(KernelApiError, match="only serves the 'replicad' kernel"):
        client.render(dag={}, kernel="truck", format="stl")


def test_socket_rejects_featurescript_and_manifest(socket_path):
    client = KernelApiClient(socket_path=socket_path)
    with pytest.raises(KernelApiError, match="does not serve generate_featurescript"):
        client.generate_featurescript(dag={})
    with pytest.raises(KernelApiError, match="does not serve export_assembly_stl_manifest"):
        client.export_assembly_stl_manifest(dag={})


def test_failed_render_resets_stale_warnings(socket_path):
    calls = {"n": 0}

    def _ok_then_error(request: dict) -> dict:
        calls["n"] += 1
        if calls["n"] == 1:
            return _ok_reply(request)
        return {
            "id": request.get("id"),
            "ok": False,
            "error": {"code": "kernel_error", "message": "boom"},
        }

    sidecar = FakeSidecar(socket_path, _ok_then_error)
    try:
        client = KernelApiClient(socket_path=socket_path)
        client.download_stl(dag={"rootNodeId": "0"})
        assert client.last_assembly_warnings  # first render reported findings
        with pytest.raises(KernelApiError, match="boom"):
            client.download_stl(dag={"rootNodeId": "0"})
        # A failed render must not leave the previous render's findings behind.
        assert client.last_assembly_warnings is None
    finally:
        sidecar.close()


def test_unreachable_socket_raises_with_clear_message(tmp_path):
    client = KernelApiClient(socket_path=str(tmp_path / "missing.sock"), timeout_s=1.0)
    with pytest.raises(KernelApiError, match="not reachable"):
        client.download_stl(dag={"rootNodeId": "0"})


def test_empty_warnings_normalize_to_empty_list(socket_path):
    def _no_warning_reply(request: dict) -> dict:
        return {
            "id": request.get("id"),
            "ok": True,
            "format": "stl",
            "stl_base64": base64.b64encode(FAKE_STL).decode(),
        }

    sidecar = FakeSidecar(socket_path, _no_warning_reply)
    try:
        client = KernelApiClient(socket_path=socket_path)
        client.download_stl(dag={"rootNodeId": "0"})
        # The sidecar checked and reported nothing — [] (checked, clean), not None.
        assert client.last_assembly_warnings == []
    finally:
        sidecar.close()


def test_health_pings_the_socket(socket_path):
    sidecar = FakeSidecar(socket_path, _ok_reply)
    try:
        client = KernelApiClient(socket_path=socket_path)
        assert client.health() == {"status": "ok", "transport": "socket"}
        assert sidecar.requests[0]["op"] == "ping"
    finally:
        sidecar.close()
