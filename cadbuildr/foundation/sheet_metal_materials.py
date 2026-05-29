"""Sheet metal material library.

Standard alloys + US/metric gauge tables, with per-material K-factor and
minimum-bend-radius rules. Used by ``SheetMetalConfig`` and by the
``base_flange`` / ``edge_flange`` / ``bend`` helpers to resolve material
choice into the geometric parameters the runtime needs (thickness, bend
radius, K-factor).

The K-factor model follows the empirical curve used in most shop-floor
guides:

    K = clamp(0.5 - a * exp(-b * r/t), k_min, 0.5)

The neutral fiber sits at the mid-thickness for very loose bends
(``r/t`` large) and shifts toward the inside surface for tight bends.
The per-material constants ``k_a``/``k_b``/``k_min`` are tuned so that
``r/t = 1`` lands near the table values from the Machinery's Handbook
(typically 0.33–0.42 for common alloys).

All values are *guidance*, not warranties — if a shop has its own bend
deduction table, override the resolved K-factor explicitly per op.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Mapping, Optional


@dataclass(frozen=True)
class SheetMetalMaterial:
    """A sheet-metal alloy with its standard fabrication properties.

    Attributes:
        name: Human-readable identifier (e.g. ``"AISI 304 stainless"``).
        density: kg / m^3 — used for mass / weight estimates.
        yield_strength: MPa — informational only.
        min_bend_radius_ratio: smallest inside bend radius the alloy
            tolerates without cracking, expressed as a multiple of
            material thickness. Bending tighter than this raises a
            warning (or a ``ValueError`` if ``strict_min_radius`` is on).
        k_a, k_b, k_min: parameters of the empirical K-factor curve.
            See module docstring.
        default_k_factor: fallback K-factor when the curve can't be
            evaluated (e.g. callers passing a placeholder bend radius).
        gauge_table: ``{gauge: thickness_mm}`` for the alloy's stock
            sheet sizes. US gauges differ by family — galvanized steel
            uses a different table from cold-rolled steel from
            aluminum. Each material carries its own table.
    """

    name: str
    density: float
    yield_strength: float
    min_bend_radius_ratio: float
    k_a: float = 0.35
    k_b: float = 0.5
    k_min: float = 0.33
    default_k_factor: float = 0.40
    gauge_table: Mapping[int, float] = field(default_factory=dict)

    def thickness_for_gauge(self, gauge: int) -> float:
        """Return the nominal thickness (mm) for a US gauge number.

        Raises ``ValueError`` if the alloy does not stock that gauge.
        """
        if gauge not in self.gauge_table:
            available = sorted(self.gauge_table.keys())
            raise ValueError(
                f"Material '{self.name}' has no gauge {gauge}. "
                f"Available gauges: {available}"
            )
        return self.gauge_table[gauge]

    def recommended_bend_radius(self, thickness: float) -> float:
        """Smallest bend radius the alloy supports at this thickness.

        Equal to ``min_bend_radius_ratio * thickness``.
        """
        return self.min_bend_radius_ratio * thickness

    def k_factor(self, bend_radius: float, thickness: float) -> float:
        """Recommended K-factor for the given bend geometry.

        For ``thickness <= 0`` returns ``default_k_factor`` rather than
        raising — callers may pass placeholders during DAG construction.
        """
        if thickness <= 0:
            return self.default_k_factor
        ratio = bend_radius / thickness
        k = 0.5 - self.k_a * math.exp(-self.k_b * ratio)
        return min(0.5, max(self.k_min, k))

    def validate_bend(
        self,
        bend_radius: float,
        thickness: float,
        *,
        strict: bool = False,
    ) -> Optional[str]:
        """Check that the bend is producible. Returns a warning message
        (or ``None`` if OK). Raises ``ValueError`` when ``strict`` is on.
        """
        if thickness <= 0:
            return None
        min_radius = self.recommended_bend_radius(thickness)
        if bend_radius < min_radius - 1e-9:
            msg = (
                f"Bend radius {bend_radius:.3f} mm is below "
                f"{self.name}'s minimum of {min_radius:.3f} mm "
                f"({self.min_bend_radius_ratio}× thickness {thickness:.3f} mm). "
                "Expect cracking or grain failure."
            )
            if strict:
                raise ValueError(msg)
            return msg
        return None


# ---------------------------------------------------------------------------
# US gauge tables (thickness in mm)
# ---------------------------------------------------------------------------

# Cold-rolled / hot-rolled mild steel — Manufacturers' Standard Gauge.
_STEEL_GAUGE_TABLE: Dict[int, float] = {
    7: 4.554,
    8: 4.176,
    9: 3.797,
    10: 3.416,
    11: 3.038,
    12: 2.657,
    13: 2.278,
    14: 1.897,
    15: 1.709,
    16: 1.519,
    17: 1.367,
    18: 1.214,
    19: 1.062,
    20: 0.912,
    21: 0.836,
    22: 0.759,
    23: 0.683,
    24: 0.607,
    25: 0.531,
    26: 0.454,
    27: 0.417,
    28: 0.378,
    29: 0.343,
    30: 0.305,
}

# Galvanized steel — slightly thicker per gauge than uncoated (the zinc
# coating adds ~0.05 mm).
_GALV_STEEL_GAUGE_TABLE: Dict[int, float] = {
    g: round(t + 0.057, 3) for g, t in _STEEL_GAUGE_TABLE.items()
}

# Stainless steel — same Manufacturers' Standard table as carbon steel.
_STAINLESS_GAUGE_TABLE: Dict[int, float] = dict(_STEEL_GAUGE_TABLE)

# Aluminum / non-ferrous — Brown & Sharpe (AWG) gauge.
_ALUMINUM_GAUGE_TABLE: Dict[int, float] = {
    6: 4.115,
    7: 3.665,
    8: 3.264,
    9: 2.906,
    10: 2.588,
    11: 2.304,
    12: 2.052,
    13: 1.828,
    14: 1.628,
    15: 1.450,
    16: 1.291,
    17: 1.150,
    18: 1.024,
    19: 0.912,
    20: 0.813,
    21: 0.724,
    22: 0.643,
    23: 0.574,
    24: 0.511,
    25: 0.455,
    26: 0.404,
    27: 0.361,
    28: 0.320,
    29: 0.287,
    30: 0.254,
}

# Copper / brass — Brown & Sharpe.
_COPPER_GAUGE_TABLE: Dict[int, float] = dict(_ALUMINUM_GAUGE_TABLE)


# ---------------------------------------------------------------------------
# Standard alloy library
# ---------------------------------------------------------------------------

COLD_ROLLED_STEEL = SheetMetalMaterial(
    name="Cold Rolled Steel (CRS, SAE 1008)",
    density=7870.0,
    yield_strength=170.0,
    min_bend_radius_ratio=0.5,
    k_a=0.32,
    k_b=0.55,
    k_min=0.36,
    default_k_factor=0.40,
    gauge_table=_STEEL_GAUGE_TABLE,
)

HOT_ROLLED_STEEL = SheetMetalMaterial(
    name="Hot Rolled Steel (HRS, A36)",
    density=7850.0,
    yield_strength=250.0,
    min_bend_radius_ratio=1.0,
    k_a=0.32,
    k_b=0.55,
    k_min=0.36,
    default_k_factor=0.40,
    gauge_table=_STEEL_GAUGE_TABLE,
)

GALVANIZED_STEEL = SheetMetalMaterial(
    name="Galvanized Steel (G90)",
    density=7870.0,
    yield_strength=205.0,
    min_bend_radius_ratio=0.5,
    k_a=0.30,
    k_b=0.55,
    k_min=0.36,
    default_k_factor=0.41,
    gauge_table=_GALV_STEEL_GAUGE_TABLE,
)

STAINLESS_304 = SheetMetalMaterial(
    name="Stainless 304 (annealed)",
    density=8000.0,
    yield_strength=215.0,
    min_bend_radius_ratio=1.0,
    k_a=0.27,
    k_b=0.45,
    k_min=0.38,
    default_k_factor=0.43,
    gauge_table=_STAINLESS_GAUGE_TABLE,
)

STAINLESS_316 = SheetMetalMaterial(
    name="Stainless 316 (annealed)",
    density=8000.0,
    yield_strength=205.0,
    min_bend_radius_ratio=1.0,
    k_a=0.27,
    k_b=0.45,
    k_min=0.38,
    default_k_factor=0.43,
    gauge_table=_STAINLESS_GAUGE_TABLE,
)

ALUMINUM_5052_H32 = SheetMetalMaterial(
    name="Aluminum 5052-H32",
    density=2680.0,
    yield_strength=193.0,
    min_bend_radius_ratio=0.5,
    k_a=0.35,
    k_b=0.50,
    k_min=0.33,
    default_k_factor=0.36,
    gauge_table=_ALUMINUM_GAUGE_TABLE,
)

ALUMINUM_6061_T6 = SheetMetalMaterial(
    name="Aluminum 6061-T6",
    density=2700.0,
    yield_strength=276.0,
    min_bend_radius_ratio=3.0,
    k_a=0.35,
    k_b=0.50,
    k_min=0.33,
    default_k_factor=0.36,
    gauge_table=_ALUMINUM_GAUGE_TABLE,
)

ALUMINUM_3003_H14 = SheetMetalMaterial(
    name="Aluminum 3003-H14",
    density=2730.0,
    yield_strength=145.0,
    min_bend_radius_ratio=0.5,
    k_a=0.35,
    k_b=0.50,
    k_min=0.33,
    default_k_factor=0.36,
    gauge_table=_ALUMINUM_GAUGE_TABLE,
)

BRASS_260 = SheetMetalMaterial(
    name="Brass C260 (cartridge brass)",
    density=8530.0,
    yield_strength=124.0,
    min_bend_radius_ratio=0.5,
    k_a=0.30,
    k_b=0.50,
    k_min=0.35,
    default_k_factor=0.38,
    gauge_table=_COPPER_GAUGE_TABLE,
)

COPPER_C110 = SheetMetalMaterial(
    name="Copper C110",
    density=8960.0,
    yield_strength=70.0,
    min_bend_radius_ratio=0.5,
    k_a=0.32,
    k_b=0.50,
    k_min=0.35,
    default_k_factor=0.38,
    gauge_table=_COPPER_GAUGE_TABLE,
)


MATERIALS: Dict[str, SheetMetalMaterial] = {
    "cold_rolled_steel": COLD_ROLLED_STEEL,
    "hot_rolled_steel": HOT_ROLLED_STEEL,
    "galvanized_steel": GALVANIZED_STEEL,
    "stainless_304": STAINLESS_304,
    "stainless_316": STAINLESS_316,
    "aluminum_5052": ALUMINUM_5052_H32,
    "aluminum_5052_h32": ALUMINUM_5052_H32,
    "aluminum_6061": ALUMINUM_6061_T6,
    "aluminum_6061_t6": ALUMINUM_6061_T6,
    "aluminum_3003": ALUMINUM_3003_H14,
    "brass": BRASS_260,
    "brass_260": BRASS_260,
    "copper": COPPER_C110,
    "copper_c110": COPPER_C110,
}


def get_material(name: str) -> SheetMetalMaterial:
    """Look up a stock material by key (case-insensitive)."""
    key = name.strip().lower().replace("-", "_").replace(" ", "_")
    if key not in MATERIALS:
        available = sorted({m.name for m in MATERIALS.values()})
        raise KeyError(
            f"Unknown sheet metal material '{name}'. Known: {available}"
        )
    return MATERIALS[key]


__all__ = [
    "SheetMetalMaterial",
    "COLD_ROLLED_STEEL",
    "HOT_ROLLED_STEEL",
    "GALVANIZED_STEEL",
    "STAINLESS_304",
    "STAINLESS_316",
    "ALUMINUM_5052_H32",
    "ALUMINUM_6061_T6",
    "ALUMINUM_3003_H14",
    "BRASS_260",
    "COPPER_C110",
    "MATERIALS",
    "get_material",
]
