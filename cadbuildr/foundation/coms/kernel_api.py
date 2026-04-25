from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

import requests

DEFAULT_MESH_KERNEL = "replicad"
DEFAULT_FEATURE_SCRIPT_KERNEL = "onshape-fs"
MESH_KERNEL_ALLOWLIST = frozenset({"replicad", "truck"})
FEATURE_SCRIPT_KERNEL_ALLOWLIST = frozenset({"onshape-fs"})
RENDER_FORMAT_ALLOWLIST = frozenset({"json", "stl", "step"})


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
    base_url: str = "https://kernel-api.cadbuildr.com"
    timeout_s: float = 30.0
    api_token: str | None = None

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        self.api_token = self.api_token or os.getenv("CADBUILDR_API_KEY", "").strip() or None
        self._session = requests.Session()

    def close(self) -> None:
        self._session.close()

    def health(self) -> Dict[str, Any]:
        response = self._session.get(f"{self.base_url}/health", timeout=self.timeout_s)
        response.raise_for_status()
        return response.json()

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
