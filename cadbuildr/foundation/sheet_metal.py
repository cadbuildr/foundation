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
    CustomOpenShape,
    EdgeFinder,
    EdgeRef,
    FloatParameter,
    Line,
    Plane,
    Point3D,
    Sketch,
    StringParameter,
    Unfold,
    # sheet-metal operation nodes
    SheetMetalBaseFlange,
    SheetMetalClosedCorner,
    SheetMetalCornerRelief,
    SheetMetalEdgeFlange,
    SheetMetalFold,
    SheetMetalHem,
    SheetMetalJog,
    SheetMetalLoftedBend,
    SheetMetalMiterFlange,
    SheetMetalSketchedBend,
    SheetMetalTab,
    SheetMetalToSolid,
    # enums
    BendPosition,
    CornerReliefType,
    CornerType,
    DimensionPosition,
    FlangePosition,
    HemType,
    ReliefType,
    SheetDirection,
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


# ---------------------------------------------------------------------------
# Sheet-metal OPERATIONS are nodes, not helper functions: construct the
# generated classes directly (like Extrusion / Lathe) —
#   SheetMetalBaseFlange, SheetMetalTab, SheetMetalEdgeFlange,
#   SheetMetalMiterFlange, SheetMetalHem, SheetMetalSketchedBend,
#   SheetMetalJog, SheetMetalClosedCorner, SheetMetalCornerRelief,
#   SheetMetalLoftedBend, SheetMetalToSolid, Unfold, SheetMetalFold.
# Ergonomics are declared in the schema: enum fields accept their string value,
# and an EdgeRef field accepts a bare Line (or EdgeFinder) via @cast. This
# module now only carries material/config data, not operation wrappers.
# ---------------------------------------------------------------------------

__all__ = [
    "SheetMetalConfig",
    "SheetMetalMaterial",
    "MATERIALS",
    "get_material",
    "set_default_config",
    "get_default_config",
]
