"""Shared screenshot framing payload for broker / viewer (matches TS ScreenshotFramingDetail)."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

STANDARD_VIEWS = frozenset(
    {"iso", "current", "top", "bottom", "left", "right", "front", "back"}
)


def _as_triple(value: Any) -> Optional[Tuple[float, float, float]]:
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    try:
        return (float(value[0]), float(value[1]), float(value[2]))
    except (TypeError, ValueError):
        return None


def build_screenshot_framing(
    *,
    view: Optional[str] = None,
    plane: Optional[str] = None,
    zoom: Optional[float] = None,
    camera_position: Optional[Any] = None,
    target: Optional[Any] = None,
    up: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Build the JSON `framing` object sent to the broker / viewer.

    `plane` is accepted as a legacy alias for `view` (case-insensitive).
    """
    effective = (view or "").strip().lower() if view else None
    if not effective and plane:
        effective = str(plane).strip().lower()

    if not effective:
        effective = "iso"
    if effective not in STANDARD_VIEWS:
        raise ValueError(
            f"Invalid view {effective!r}; expected one of {sorted(STANDARD_VIEWS)}"
        )

    framing: Dict[str, Any] = {"view": effective}

    if zoom is not None:
        framing["zoom"] = float(zoom)

    eye = _as_triple(camera_position)
    tgt = _as_triple(target)
    upv = _as_triple(up)
    if eye is not None:
        framing["camera_position"] = list(eye)
    if tgt is not None:
        framing["target"] = list(tgt)
    if upv is not None:
        framing["up"] = list(upv)

    return framing


def request_viewer_screenshot(
    *,
    broker_url: Optional[str] = None,
    view: Optional[str] = None,
    plane: Optional[str] = None,
    zoom: Optional[float] = None,
    camera_position: Optional[Any] = None,
    target: Optional[Any] = None,
    up: Optional[Any] = None,
    image_format: str = "png",
    timeout: float = 15.0,
) -> Dict[str, Any]:
    """
    POST /screenshot/request with optional framing; returns parsed JSON (status, data_url, ...).
    """
    try:
        import requests
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("requests is required for request_viewer_screenshot") from exc

    base = (broker_url or "http://localhost:5050").rstrip("/")
    framing = build_screenshot_framing(
        view=view,
        plane=plane,
        zoom=zoom,
        camera_position=camera_position,
        target=target,
        up=up,
    )
    payload: Dict[str, Any] = {"format": image_format, "framing": framing}
    response = requests.post(f"{base}/screenshot/request", json=payload, timeout=timeout)
    try:
        data = response.json()
    except Exception:
        data = {"status": "error", "message": response.text}
    if not isinstance(data, dict):
        return {"status": "error", "message": "Invalid JSON from broker"}
    return data
