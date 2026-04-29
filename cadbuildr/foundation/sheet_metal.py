"""Sheet metal ergonomic helpers.

Thin wrappers around the generated Pydantic models that accept plain Python
numbers / strings and return native sheet-metal operation objects ready to feed
into a Part.

A SheetMetalConfig instance holds project-level defaults (thickness,
bend_radius, k_factor) so consumers don't repeat themselves on every call.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from .gen.models import (
    BoolParameter,
    EdgeFinder,
    FloatParameter,
    Sketch,
    SheetMetalBaseFlange,
    SheetMetalBend,
    SheetMetalContourFlange,
    SheetMetalCornerSeam,
    SheetMetalEdgeFlange,
    SheetMetalToSolid,
    StringParameter,
    Unfold,
)


@dataclass
class SheetMetalConfig:
    """Project-level sheet-metal defaults.

    These values are used as fallbacks whenever an operation does not specify
    them explicitly. Construct one per project (or per part) and pass it to
    the helper functions below via the `config=` argument or by setting it as
    the module-level default with `set_default_config(...)`.
    """

    thickness: float = 1.0
    bend_radius: float = 1.0
    k_factor: float = 0.4


_DEFAULT_CONFIG: SheetMetalConfig = SheetMetalConfig()


def set_default_config(config: SheetMetalConfig) -> None:
    """Set the module-level default config used when none is passed to helpers."""
    global _DEFAULT_CONFIG
    _DEFAULT_CONFIG = config


def get_default_config() -> SheetMetalConfig:
    return _DEFAULT_CONFIG


def _f(value) -> FloatParameter:
    return value if isinstance(value, FloatParameter) else FloatParameter(value=float(value))


def _s(value) -> StringParameter:
    return value if isinstance(value, StringParameter) else StringParameter(value=str(value))


def _b(value) -> BoolParameter:
    return value if isinstance(value, BoolParameter) else BoolParameter(value=bool(value))


def base_flange(
    profile,
    sketch: Sketch,
    *,
    thickness: Optional[float] = None,
    bend_radius: Optional[float] = None,
    k_factor: Optional[float] = None,
    direction: str = "positive",
    config: Optional[SheetMetalConfig] = None,
) -> SheetMetalBaseFlange:
    """Create a sheet-metal base flange (the foundational flat plate).

    `profile` is a ClosedShape2D, `sketch` is the Sketch the profile is drawn on.
    """
    cfg = config or _DEFAULT_CONFIG
    return SheetMetalBaseFlange(
        profile=profile,
        sketch=sketch,
        thickness=_f(thickness if thickness is not None else cfg.thickness),
        default_bend_radius=_f(bend_radius if bend_radius is not None else cfg.bend_radius),
        default_k_factor=_f(k_factor if k_factor is not None else cfg.k_factor),
        direction=_s(direction),
    )


def edge_flange(
    body,
    edge_finder: EdgeFinder,
    length: float,
    *,
    bend_angle: float = 90.0,
    bend_radius: Optional[float] = None,
    k_factor: Optional[float] = None,
    flange_position: str = "material-inside",
    relief: str = "none",
) -> SheetMetalEdgeFlange:
    """Add an edge flange (bend + flange wall) to a sheet-metal body."""
    return SheetMetalEdgeFlange(
        body=body,
        edge_finder=edge_finder,
        length=_f(length),
        bend_angle=_f(bend_angle),
        bend_radius=_f(bend_radius) if bend_radius is not None else None,
        k_factor=_f(k_factor) if k_factor is not None else None,
        flange_position=_s(flange_position),
        relief=_s(relief),
    )


def contour_flange(
    body,
    edge_finder: EdgeFinder,
    profile,
    sketch: Sketch,
    length: float,
    *,
    bend_radius: Optional[float] = None,
    k_factor: Optional[float] = None,
) -> SheetMetalContourFlange:
    """Add a sketch-driven contour flange (e.g. a lipped edge).

    `profile` is the cross-section drawn on `sketch` (a Sketch perpendicular to
    the body edge selected by `edge_finder`); the profile is swept along the
    edge for `length`.
    """
    return SheetMetalContourFlange(
        body=body,
        edge_finder=edge_finder,
        profile=profile,
        sketch=sketch,
        length=_f(length),
        bend_radius=_f(bend_radius) if bend_radius is not None else None,
        k_factor=_f(k_factor) if k_factor is not None else None,
    )


def bend(
    body,
    bend_line: EdgeFinder,
    angle: float,
    *,
    radius: Optional[float] = None,
    k_factor: Optional[float] = None,
    bend_position: str = "centered",
) -> SheetMetalBend:
    """Bend a flat region around an in-plane line."""
    return SheetMetalBend(
        body=body,
        bend_line=bend_line,
        angle=_f(angle),
        radius=_f(radius) if radius is not None else None,
        k_factor=_f(k_factor) if k_factor is not None else None,
        bend_position=_s(bend_position),
    )


def corner_seam(
    body,
    edge_finders: Sequence[EdgeFinder],
) -> SheetMetalCornerSeam:
    """Close mitered corners between adjacent flanges."""
    return SheetMetalCornerSeam(body=body, edge_finders=list(edge_finders))


def to_solid(body) -> SheetMetalToSolid:
    """Bridge a sheet-metal body into the regular solid pipeline.

    Use this on the chain's tail to add the result to a Part's operations.
    """
    return SheetMetalToSolid(body=body)


def unfold(
    body,
    fixed_face: Optional[EdgeFinder] = None,
) -> Unfold:
    """Compute the flat pattern of a sheet-metal body."""
    return Unfold(body=body, fixed_face=fixed_face) if fixed_face is not None else Unfold(body=body)


__all__ = [
    "SheetMetalConfig",
    "set_default_config",
    "get_default_config",
    "base_flange",
    "edge_flange",
    "contour_flange",
    "bend",
    "corner_seam",
    "to_solid",
    "unfold",
]
