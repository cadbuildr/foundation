from __future__ import annotations

import base64
import json
import os
import socket as _socket
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

import requests

DEFAULT_MESH_KERNEL = "replicad"
DEFAULT_FEATURE_SCRIPT_KERNEL = "onshape-fs"
MESH_KERNEL_ALLOWLIST = frozenset({"replicad", "truck"})
FEATURE_SCRIPT_KERNEL_ALLOWLIST = frozenset({"onshape-fs"})
RENDER_FORMAT_ALLOWLIST = frozenset({"json", "stl", "step"})
# Formats the local kernel sidecar (unix-socket NDJSON transport) can serve.
SOCKET_FORMAT_ALLOWLIST = frozenset({"json", "stl"})
_SOCKET_CONNECT_RETRIES = 3
_SOCKET_CONNECT_BACKOFF_S = 0.5


class KernelApiError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: Optional[str] = None,
        request_id: Optional[str] = None,
        details: Optional[object] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.request_id = request_id
        self.details = details


@dataclass
class KernelApiClient:
    """Render foundation DAGs through the CADbuildr kernel.

    Two transports behind one API:

    - HTTP (default): the managed kernel-api service (``base_url``).
    - Unix-socket sidecar: when ``CADBUILDR_KERNEL_SOCKET`` (or
      ``socket_path``) is set — the cloud sandbox runs a warm in-process
      kernel behind an NDJSON unix socket instead of a localhost HTTP
      server. Public signatures are identical; only the wire changes.

    After a socket render, ``last_assembly_warnings`` holds the kernel's
    mechanical sanity findings for that DAG (e.g. ``isolated_part`` for a
    placed-but-unfastened component) — an empty list means the kernel
    checked and found nothing; ``None`` means the transport didn't report.
    """

    base_url: str = "https://kernel-api.cadbuildr.com"
    timeout_s: float = 30.0
    api_token: str | None = None
    socket_path: str | None = None
    last_assembly_warnings: Optional[List[Dict[str, Any]]] = field(
        default=None, init=False, repr=False
    )

    def __post_init__(self) -> None:
        # Prefer explicit CAD_COMPILE_API_BASE_URL (used across dev/tests) then CADBUILDR_KERNEL_API_BASE_URL.
        env_base = (
            os.getenv("CAD_COMPILE_API_BASE_URL", "").strip()
            or os.getenv("CADBUILDR_KERNEL_API_BASE_URL", "").strip()
        )
        if env_base:
            self.base_url = env_base.rstrip("/")
        else:
            self.base_url = self.base_url.rstrip("/")
        self.api_token = self.api_token or os.getenv("CADBUILDR_API_KEY", "").strip() or None
        self.socket_path = (
            self.socket_path or os.getenv("CADBUILDR_KERNEL_SOCKET", "").strip() or None
        )
        self._session = requests.Session()

    def close(self) -> None:
        self._session.close()

    def health(self) -> Dict[str, Any]:
        if self.socket_path:
            reply = self._socket_roundtrip({"op": "ping"})
            return {"status": "ok" if reply.get("pong") else "unknown", "transport": "socket"}
        response = self._session.get(f"{self.base_url}/health", timeout=self.timeout_s)
        response.raise_for_status()
        return response.json()

    # ── unix-socket sidecar transport ────────────────────────────────────

    def _socket_roundtrip(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """One NDJSON request/response over a fresh unix-socket connection.

        The sidecar serializes compile work internally; short-lived
        connections keep this client fork/thread-safe with zero pooling.
        """
        assert self.socket_path is not None
        request = {"id": request.get("id") or uuid.uuid4().hex, **request}
        payload = (json.dumps(request) + "\n").encode("utf-8")

        conn: Optional[_socket.socket] = None
        last_err: Optional[Exception] = None
        for attempt in range(_SOCKET_CONNECT_RETRIES):
            conn = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
            conn.settimeout(self.timeout_s)
            try:
                conn.connect(self.socket_path)
                break
            except OSError as err:
                conn.close()
                conn = None
                last_err = err
                # The sidecar may still be booting right after sandbox start.
                if attempt < _SOCKET_CONNECT_RETRIES - 1:
                    time.sleep(_SOCKET_CONNECT_BACKOFF_S * (attempt + 1))
        if conn is None:
            raise KernelApiError(
                f"Kernel sidecar socket not reachable at {self.socket_path}: {last_err}",
                code="socket_unreachable",
            )

        try:
            conn.sendall(payload)
            buf = bytearray()
            while b"\n" not in buf:
                try:
                    chunk = conn.recv(1 << 20)
                except TimeoutError as err:
                    raise KernelApiError(
                        f"Kernel sidecar timed out after {self.timeout_s}s "
                        f"(socket {self.socket_path})",
                        code="socket_timeout",
                    ) from err
                if not chunk:
                    raise KernelApiError(
                        "Kernel sidecar closed the connection before replying "
                        f"(socket {self.socket_path})",
                        code="socket_closed",
                    )
                buf.extend(chunk)
        finally:
            conn.close()

        line = bytes(buf).split(b"\n", 1)[0]
        try:
            reply = json.loads(line.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as err:
            raise KernelApiError("Kernel sidecar returned invalid JSON") from err

        if not isinstance(reply, dict):
            raise KernelApiError("Kernel sidecar returned a non-object reply")
        if not reply.get("ok"):
            err_obj = reply.get("error") or {}
            raise KernelApiError(
                str(err_obj.get("message", "Kernel sidecar request failed")),
                code=err_obj.get("code"),
                request_id=str(reply.get("id")) if reply.get("id") is not None else None,
                details=err_obj.get("details"),
            )
        return reply

    def _render_via_socket(
        self,
        *,
        dag: Dict[str, Any],
        render_format: str,
        mesh_config: Optional[Dict[str, Any]],
        request_id: Optional[str],
    ) -> Dict[str, Any] | bytes:
        request: Dict[str, Any] = {"dag": dag, "format": render_format}
        if request_id:
            request["id"] = request_id
        if mesh_config:
            request["meshConfig"] = mesh_config
        reply = self._socket_roundtrip(request)

        warnings = reply.get("assemblyWarnings")
        self.last_assembly_warnings = warnings if isinstance(warnings, list) else []

        if render_format == "stl":
            stl_b64 = reply.get("stl_base64")
            if not isinstance(stl_b64, str):
                raise KernelApiError("Kernel sidecar STL reply is missing stl_base64")
            return base64.b64decode(stl_b64)
        return {
            "format": "json",
            "mesh": reply.get("mesh"),
            "assemblyWarnings": self.last_assembly_warnings,
        }

    @staticmethod
    def _resolve_kernel(
        kernel: Optional[str],
        *,
        default_kernel: str,
        allowlist: frozenset[str],
        endpoint_name: str,
    ) -> str:
        selected_kernel = kernel or default_kernel
        if selected_kernel not in allowlist:
            allowed = ", ".join(sorted(allowlist))
            raise ValueError(
                f"Unsupported kernel '{selected_kernel}' for {endpoint_name}. "
                f"Allowed kernels: {allowed}"
            )
        return selected_kernel

    @staticmethod
    def _resolve_format(format: str) -> str:
        selected = (format or "json").strip().lower()
        if selected not in RENDER_FORMAT_ALLOWLIST:
            allowed = ", ".join(sorted(RENDER_FORMAT_ALLOWLIST))
            raise ValueError(f"Unsupported render format '{format}'. Allowed formats: {allowed}")
        return selected

    def _headers(self, request_id: Optional[str]) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if request_id:
            headers["x-request-id"] = request_id
        if self.api_token:
            headers["authorization"] = f"Bearer {self.api_token}"
            headers["x-api-key"] = self.api_token
        return headers

    def render(
        self,
        *,
        dag: Dict[str, Any],
        kernel: Optional[str] = None,
        format: Literal["json", "stl", "step"] = "json",
        mesh_config: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        client_request_id: Optional[str] = None,
        session_id: Optional[str] = None,
        file_name: Optional[str] = None,
    ) -> Dict[str, Any] | bytes:
        mesh_kernel = self._resolve_kernel(
            kernel,
            default_kernel=DEFAULT_MESH_KERNEL,
            allowlist=MESH_KERNEL_ALLOWLIST,
            endpoint_name="render",
        )
        render_format = self._resolve_format(format)

        # Reset per render: a failed render must not leave the PREVIOUS
        # render's findings behind for callers that check after catching.
        self.last_assembly_warnings = None

        if self.socket_path:
            if mesh_kernel != DEFAULT_MESH_KERNEL:
                raise KernelApiError(
                    f"Kernel sidecar only serves the '{DEFAULT_MESH_KERNEL}' kernel "
                    f"(requested '{mesh_kernel}')",
                    code="invalid_request",
                )
            if render_format not in SOCKET_FORMAT_ALLOWLIST:
                allowed = ", ".join(sorted(SOCKET_FORMAT_ALLOWLIST))
                raise KernelApiError(
                    f"Kernel sidecar does not support format '{render_format}' "
                    f"(allowed: {allowed})",
                    code="invalid_request",
                )
            return self._render_via_socket(
                dag=dag,
                render_format=render_format,
                mesh_config=mesh_config,
                request_id=request_id or client_request_id,
            )

        payload: Dict[str, Any] = {"dag": dag, "kernel": mesh_kernel, "format": render_format}
        if mesh_config:
            payload["meshConfig"] = mesh_config
        if client_request_id:
            payload["clientRequestId"] = client_request_id
        if session_id:
            payload["sessionId"] = session_id
        if file_name:
            payload["fileName"] = file_name

        response = self._session.post(
            f"{self.base_url}/v1/kernels/{mesh_kernel}/render",
            json=payload,
            headers=self._headers(request_id),
            timeout=self.timeout_s,
        )
        if render_format == "json":
            return self._parse_response(response)
        if response.status_code >= 400:
            self._parse_response(response)
        return response.content

    def compile_mesh(
        self,
        *,
        dag: Dict[str, Any],
        kernel: Optional[str] = None,
        mesh_config: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        client_request_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.render(
            dag=dag,
            kernel=kernel,
            format="json",
            mesh_config=mesh_config,
            request_id=request_id,
            client_request_id=client_request_id,
            session_id=session_id,
        )

    def download_stl(
        self,
        *,
        dag: Dict[str, Any],
        kernel: Optional[str] = None,
        mesh_config: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        client_request_id: Optional[str] = None,
        session_id: Optional[str] = None,
        file_name: Optional[str] = None,
    ) -> bytes:
        return self.render(
            dag=dag,
            kernel=kernel,
            format="stl",
            mesh_config=mesh_config,
            request_id=request_id,
            client_request_id=client_request_id,
            session_id=session_id,
            file_name=file_name,
        )

    def generate_featurescript(
        self,
        *,
        dag: Dict[str, Any],
        kernel: Optional[str] = None,
        request_id: Optional[str] = None,
        client_request_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if self.socket_path:
            raise KernelApiError(
                "Kernel sidecar does not serve generate_featurescript — "
                "use the managed HTTP kernel-api outside the sandbox",
                code="invalid_request",
            )
        fs_kernel = self._resolve_kernel(
            kernel,
            default_kernel=DEFAULT_FEATURE_SCRIPT_KERNEL,
            allowlist=FEATURE_SCRIPT_KERNEL_ALLOWLIST,
            endpoint_name="generate_featurescript",
        )

        payload: Dict[str, Any] = {"dag": dag, "kernel": fs_kernel}
        if client_request_id:
            payload["clientRequestId"] = client_request_id
        if session_id:
            payload["sessionId"] = session_id

        response = self._session.post(
            f"{self.base_url}/v1/kernels/{fs_kernel}/generate-featurescript",
            json=payload,
            headers=self._headers(request_id),
            timeout=self.timeout_s,
        )
        return self._parse_response(response)

    def export_assembly_stl_manifest(
        self,
        *,
        dag: Dict[str, Any],
        kernel: Optional[str] = None,
        mesh_config: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        client_request_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if self.socket_path:
            raise KernelApiError(
                "Kernel sidecar does not serve export_assembly_stl_manifest — "
                "render per-part DAGs with download_stl instead",
                code="invalid_request",
            )
        mesh_kernel = self._resolve_kernel(
            kernel,
            default_kernel=DEFAULT_MESH_KERNEL,
            allowlist=MESH_KERNEL_ALLOWLIST,
            endpoint_name="export_assembly_stl_manifest",
        )

        payload: Dict[str, Any] = {"dag": dag, "kernel": mesh_kernel}
        if mesh_config:
            payload["meshConfig"] = mesh_config
        if client_request_id:
            payload["clientRequestId"] = client_request_id
        if session_id:
            payload["sessionId"] = session_id

        response = self._session.post(
            f"{self.base_url}/v1/kernels/{mesh_kernel}/export-assembly-stl-manifest",
            json=payload,
            headers=self._headers(request_id),
            timeout=self.timeout_s,
        )
        return self._parse_response(response)

    @staticmethod
    def _parse_response(response: requests.Response) -> Dict[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            response.raise_for_status()
            raise KernelApiError("Kernel API returned invalid JSON") from exc

        if response.status_code >= 400:
            err = data.get("error", {}) if isinstance(data, dict) else {}
            if isinstance(err, dict):
                message = err.get("message", "Kernel API request failed")
                code = err.get("code")
                request_id = err.get("requestId")
                details = err.get("details")
            else:
                message = (
                    data.get("message", "Kernel API request failed")
                    if isinstance(data, dict)
                    else str(data)
                )
                code = err if isinstance(err, str) else None
                request_id = data.get("requestId") if isinstance(data, dict) else None
                details = data
            raise KernelApiError(
                message,
                code=code,
                request_id=request_id,
                details=details,
            )

        return data
