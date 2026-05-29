"""Sheet metal ergonomic helpers.

Thin wrappers around the generated Pydantic models that accept plain Python
numbers / strings and return native sheet-metal operation objects ready to feed
into a Part.

A :class:`SheetMetalConfig` instance holds project-level defaults (material,
thickness, bend radius, K-factor) so consumers don't repeat themselves on
every call. The config can be built from a stock material + gauge:

    config = SheetMetalConfig.from_material(MATERIALS["aluminum_5052"], gauge=18)
    set_default_config(config)

or from raw numbers (back-compat with the original simple API):

    config = SheetMetalConfig(thickness=2.0, bend_radius=2.0, k_factor=0.40)

When an operation does not specify a value, the config's resolved fields are
used. If a material is attached, the bend radius and K-factor default to the
material's recommendations rather than fixed numbers.

The DXF flat-pattern exporter for unfolded bodies lives in
:mod:`cadbuildr.foundation.sheet_metal_dxf`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
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
from .sheet_metal_materials import (  # re-export for convenience
    MATERIALS,
    SheetMetalMaterial,
    get_material,
)

_log = logging.getLogger(__name__)


@dataclass
class SheetMetalConfig:
    """Project-level sheet-metal defaults.

    Construct one per part or per project and pass it through ``config=`` on
    each helper, or install it as the module-level default with
    :func:`set_default_config`.

    The plain attributes ``thickness`` / ``bend_radius`` / ``k_factor`` are
    the *resolved* values used by the helpers. They can be set directly or
    derived from a stock material via :meth:`from_material`.

    Attributes:
        thickness: Stock thickness in mm.
        bend_radius: Default inside bend radius in mm.
        k_factor: Default K-factor (neutral-fiber location, 0.33..0.50).
        material: Optional reference to a SheetMetalMaterial. When set, the
            helpers will infer a per-bend K-factor from the material's curve
            if the caller does not specify one explicitly, and will also
            check the bend radius against the material's minimum.
        strict_min_radius: If ``True``, the helpers raise on bend radii
            below the material's minimum instead of just logging a warning.
    """

    thickness: float = 1.0
    bend_radius: float = 1.0
    k_factor: float = 0.40
    material: Optional[SheetMetalMaterial] = None
    strict_min_radius: bool = False

    @classmethod
    def from_material(
        cls,
        material: SheetMetalMaterial,
        *,
        gauge: Optional[int] = None,
        thickness: Optional[float] = None,
        bend_radius: Optional[float] = None,
        k_factor: Optional[float] = None,
        strict_min_radius: bool = False,
    ) -> "SheetMetalConfig":
        """Build a config from a stock material.

        Exactly one of ``gauge`` or ``thickness`` must be provided. When
        ``bend_radius`` is omitted it defaults to the material's recommended
        minimum (``min_bend_radius_ratio × thickness``); when ``k_factor``
        is omitted it is computed from the material's K-factor curve at the
        chosen ``bend_radius / thickness`` ratio.
        """
        if (gauge is None) == (thickness is None):
            raise ValueError(
                "from_material requires exactly one of `gauge` or `thickness`"
            )
        resolved_thickness = (
            material.thickness_for_gauge(gauge) if gauge is not None else float(thickness)
        )
        resolved_bend_radius = (
            float(bend_radius)
            if bend_radius is not None
            else material.recommended_bend_radius(resolved_thickness)
        )
        resolved_k = (
            float(k_factor)
            if k_factor is not None
            else material.k_factor(resolved_bend_radius, resolved_thickness)
        )
        return cls(
            thickness=resolved_thickness,
            bend_radius=resolved_bend_radius,
            k_factor=resolved_k,
            material=material,
            strict_min_radius=strict_min_radius,
        )

    def resolve_bend(
        self,
        *,
        radius: Optional[float] = None,
        k_factor: Optional[float] = None,
    ) -> tuple[float, float]:
        """Resolve per-bend radius + K-factor against the config / material.

        - ``radius=None`` → use ``self.bend_radius``.
        - ``k_factor=None`` → use material's curve at the resolved radius
          if a material is attached, else ``self.k_factor``.
        - If a material is attached, validate the bend radius is producible
          and either log a warning or raise according to
          ``self.strict_min_radius``.
        """
        r = float(radius) if radius is not None else self.bend_radius
        if self.material is not None:
            warning = self.material.validate_bend(
                r, self.thickness, strict=self.strict_min_radius
            )
            if warning is not None:
                _log.warning(warning)
        if k_factor is not None:
            k = float(k_factor)
        elif self.material is not None:
            k = self.material.k_factor(r, self.thickness)
        else:
            k = self.k_factor
        return r, k


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

    ``profile`` is a ClosedShape2D; ``sketch`` is the Sketch it is drawn on.
    Per-call ``thickness`` / ``bend_radius`` / ``k_factor`` override the
    config; values left as ``None`` fall back to the active config (which
    in turn may have been built from a stock material via
    :meth:`SheetMetalConfig.from_material`).
    """
    cfg = config or _DEFAULT_CONFIG
    t = thickness if thickness is not None else cfg.thickness
    r, k = cfg.resolve_bend(radius=bend_radius, k_factor=k_factor)
    return SheetMetalBaseFlange(
        profile=profile,
        sketch=sketch,
        thickness=_f(t),
        default_bend_radius=_f(r),
        default_k_factor=_f(k),
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
    config: Optional[SheetMetalConfig] = None,
) -> SheetMetalEdgeFlange:
    """Add an edge flange (bend + flange wall) to a sheet-metal body.

    ``bend_radius`` and ``k_factor`` default to the body's own defaults
    when omitted at the op level; pass a ``config`` to resolve against
    a material here instead.

    ``flange_position`` is one of ``"material-inside"`` /
    ``"material-outside"`` / ``"bend-from-virtual-sharp"`` and matches
    the SolidWorks convention. ``relief`` is one of ``"none"`` /
    ``"rectangular"`` / ``"obround"`` / ``"tear"``.
    """
    if config is not None:
        r, k = config.resolve_bend(radius=bend_radius, k_factor=k_factor)
    else:
        r = bend_radius
        k = k_factor
    return SheetMetalEdgeFlange(
        body=body,
        edge_finder=edge_finder,
        length=_f(length),
        bend_angle=_f(bend_angle),
        bend_radius=_f(r) if r is not None else None,
        k_factor=_f(k) if k is not None else None,
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
    config: Optional[SheetMetalConfig] = None,
) -> SheetMetalContourFlange:
    """Add a sketch-driven contour flange (e.g. a lipped edge).

    ``profile`` is the cross-section drawn on ``sketch`` (perpendicular to
    the body edge selected by ``edge_finder``); it is swept along the edge
    for ``length``.
    """
    if config is not None:
        r, k = config.resolve_bend(radius=bend_radius, k_factor=k_factor)
    else:
        r = bend_radius
        k = k_factor
    return SheetMetalContourFlange(
        body=body,
        edge_finder=edge_finder,
        profile=profile,
        sketch=sketch,
        length=_f(length),
        bend_radius=_f(r) if r is not None else None,
        k_factor=_f(k) if k is not None else None,
    )


def bend(
    body,
    bend_line: EdgeFinder,
    angle: float,
    *,
    radius: Optional[float] = None,
    k_factor: Optional[float] = None,
    bend_position: str = "centered",
    config: Optional[SheetMetalConfig] = None,
) -> SheetMetalBend:
    """Bend a region of an existing sheet-metal body around an in-plane line.

    ``bend_position`` controls which side of the bend line is rotated and
    where the bend region sits relative to the line:
    ``"centered"`` (default), ``"material-inside"``, ``"material-outside"``.
    """
    if config is not None:
        r, k = config.resolve_bend(radius=radius, k_factor=k_factor)
    else:
        r = radius
        k = k_factor
    return SheetMetalBend(
        body=body,
        bend_line=bend_line,
        angle=_f(angle),
        radius=_f(r) if r is not None else None,
        k_factor=_f(k) if k is not None else None,
        bend_position=_s(bend_position),
    )


def corner_seam(
    body,
    edge_finders: Sequence[EdgeFinder],
    *,
    gap: float = 0.0,
) -> SheetMetalCornerSeam:
    """Close mitered corners between adjacent flanges, optionally with a gap."""
    return SheetMetalCornerSeam(
        body=body,
        edge_finders=list(edge_finders),
        gap=_f(gap),
    )


def to_solid(body) -> SheetMetalToSolid:
    """Bridge a sheet-metal body into the regular solid pipeline.

    Use this on the chain's tail to add the result to a Part's operations.
    """
    return SheetMetalToSolid(body=body)


def unfold(
    body,
    fixed_face: Optional[EdgeFinder] = None,
) -> Unfold:
    """Compute the flat pattern of a sheet-metal body.

    The result is itself a sheet-metal body whose bend regions have been
    replaced by neutral-fiber arc-length flat strips. Bend lines are
    preserved on the unfolded body as marked edges so downstream DXF
    export can lay them out on a dedicated layer.
    """
    return (
        Unfold(body=body, fixed_face=fixed_face)
        if fixed_face is not None
        else Unfold(body=body)
    )


__all__ = [
    "SheetMetalConfig",
    "SheetMetalMaterial",
    "MATERIALS",
    "get_material",
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
