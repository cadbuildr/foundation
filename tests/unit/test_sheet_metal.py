"""Tests for the sheet metal material library, config, and helpers."""

import math

import pytest

from cadbuildr.foundation.sheet_metal import (
    MATERIALS,
    SheetMetalConfig,
    SheetMetalMaterial,
    base_flange,
    bend,
    contour_flange,
    edge_flange,
    get_material,
)
from cadbuildr.foundation.sheet_metal_materials import (
    ALUMINUM_5052_H32,
    ALUMINUM_6061_T6,
    COLD_ROLLED_STEEL,
    STAINLESS_304,
)


def test_steel_gauge_table_matches_manufacturers_standard():
    # 16ga steel ≈ 0.0598" = 1.519 mm
    assert math.isclose(COLD_ROLLED_STEEL.thickness_for_gauge(16), 1.519, abs_tol=1e-3)
    # 22ga steel ≈ 0.0299" = 0.759 mm
    assert math.isclose(COLD_ROLLED_STEEL.thickness_for_gauge(22), 0.759, abs_tol=1e-3)


def test_aluminum_gauge_table_uses_brown_and_sharpe():
    # 16 B&S = 0.0508" = 1.291 mm
    assert math.isclose(ALUMINUM_5052_H32.thickness_for_gauge(16), 1.291, abs_tol=1e-3)


def test_unknown_gauge_raises():
    with pytest.raises(ValueError, match="no gauge"):
        COLD_ROLLED_STEEL.thickness_for_gauge(999)


def test_recommended_bend_radius_scales_with_thickness():
    # Aluminum 6061-T6 has min_bend_radius_ratio = 3.0
    assert math.isclose(ALUMINUM_6061_T6.recommended_bend_radius(1.5), 4.5)
    # 5052-H32 has min_bend_radius_ratio = 0.5
    assert math.isclose(ALUMINUM_5052_H32.recommended_bend_radius(1.5), 0.75)


def test_k_factor_curve_monotone_in_ratio():
    """K-factor should grow with r/t and saturate at 0.5."""
    m = COLD_ROLLED_STEEL
    t = 1.0
    ks = [m.k_factor(r, t) for r in [0.5, 1.0, 2.0, 4.0, 10.0]]
    assert all(a <= b + 1e-9 for a, b in zip(ks, ks[1:])), f"non-monotone: {ks}"
    assert 0.33 <= ks[0] <= 0.50
    assert ks[-1] <= 0.50 + 1e-9
    assert ks[-1] > ks[0] + 0.01  # actually changes


def test_k_factor_zero_thickness_returns_default():
    assert COLD_ROLLED_STEEL.k_factor(1.0, 0.0) == COLD_ROLLED_STEEL.default_k_factor


def test_validate_bend_warns_below_minimum():
    msg = ALUMINUM_6061_T6.validate_bend(0.5, 1.5)
    assert msg is not None
    assert "minimum" in msg


def test_validate_bend_strict_raises():
    with pytest.raises(ValueError, match="minimum"):
        ALUMINUM_6061_T6.validate_bend(0.5, 1.5, strict=True)


def test_validate_bend_ok_above_minimum_returns_none():
    assert ALUMINUM_6061_T6.validate_bend(5.0, 1.5) is None


def test_get_material_case_insensitive():
    assert get_material("Aluminum 5052") is ALUMINUM_5052_H32
    assert get_material("STAINLESS_304") is STAINLESS_304
    assert get_material("aluminum-5052") is ALUMINUM_5052_H32


def test_get_material_unknown_raises():
    with pytest.raises(KeyError, match="Unknown"):
        get_material("unobtainium")


def test_materials_dict_has_consistent_names():
    for key, mat in MATERIALS.items():
        assert isinstance(mat, SheetMetalMaterial)
        assert mat.gauge_table  # non-empty


def test_config_from_material_with_gauge():
    cfg = SheetMetalConfig.from_material(COLD_ROLLED_STEEL, gauge=16)
    assert math.isclose(cfg.thickness, 1.519, abs_tol=1e-3)
    # bend radius defaults to min recommendation: 0.5 × 1.519 ≈ 0.76
    assert math.isclose(cfg.bend_radius, 0.5 * 1.519, abs_tol=1e-3)
    # k_factor computed from curve at r/t = 0.5
    assert 0.33 <= cfg.k_factor <= 0.50
    assert cfg.material is COLD_ROLLED_STEEL


def test_config_from_material_with_thickness():
    cfg = SheetMetalConfig.from_material(ALUMINUM_5052_H32, thickness=2.0)
    assert cfg.thickness == 2.0
    assert math.isclose(cfg.bend_radius, 1.0)  # 0.5 × 2.0


def test_config_from_material_overrides():
    cfg = SheetMetalConfig.from_material(
        STAINLESS_304, gauge=18, bend_radius=3.0, k_factor=0.42
    )
    assert cfg.bend_radius == 3.0
    assert cfg.k_factor == 0.42


def test_config_from_material_requires_exactly_one_size():
    with pytest.raises(ValueError, match="gauge.*thickness"):
        SheetMetalConfig.from_material(COLD_ROLLED_STEEL)
    with pytest.raises(ValueError, match="gauge.*thickness"):
        SheetMetalConfig.from_material(COLD_ROLLED_STEEL, gauge=16, thickness=2.0)


def test_config_resolve_bend_uses_material_curve():
    cfg = SheetMetalConfig.from_material(COLD_ROLLED_STEEL, thickness=1.0)
    r, k = cfg.resolve_bend()
    assert math.isclose(r, cfg.bend_radius)
    assert math.isclose(k, COLD_ROLLED_STEEL.k_factor(r, 1.0))


def test_config_resolve_bend_explicit_overrides_material():
    cfg = SheetMetalConfig.from_material(COLD_ROLLED_STEEL, thickness=1.0)
    r, k = cfg.resolve_bend(radius=5.0, k_factor=0.44)
    assert r == 5.0
    assert k == 0.44


def test_config_resolve_bend_strict_min_radius_raises():
    cfg = SheetMetalConfig.from_material(
        ALUMINUM_6061_T6, thickness=2.0, strict_min_radius=True
    )
    # 6061-T6 needs r >= 3*t = 6mm; ask for 1mm.
    with pytest.raises(ValueError, match="minimum"):
        cfg.resolve_bend(radius=1.0)


def test_config_without_material_falls_back_to_fixed_k_factor():
    cfg = SheetMetalConfig(thickness=2.0, bend_radius=2.0, k_factor=0.42)
    r, k = cfg.resolve_bend()
    assert r == 2.0
    assert k == 0.42


# ---------------------------------------------------------------------------
# Helper integration: the model receives the resolved values
# ---------------------------------------------------------------------------


def _make_rect_profile():
    """Build a minimal closed profile for base_flange testing."""
    from cadbuildr.foundation import Part, Rectangle, Sketch

    class _Holder(Part):
        def __init__(self):
            self.s = Sketch(self.xy())
            self.profile = Rectangle.from_center_and_sides(self.s.origin, 40, 30)

    h = _Holder()
    return h.profile, h.s


def test_base_flange_uses_config_thickness():
    cfg = SheetMetalConfig(thickness=1.5, bend_radius=1.5, k_factor=0.40)
    profile, sketch = _make_rect_profile()
    bf = base_flange(profile=profile, sketch=sketch, config=cfg)
    assert math.isclose(bf.thickness.value, 1.5)
    assert math.isclose(bf.default_bend_radius.value, 1.5)
    assert math.isclose(bf.default_k_factor.value, 0.40)


def test_base_flange_from_material_writes_correct_defaults():
    cfg = SheetMetalConfig.from_material(COLD_ROLLED_STEEL, gauge=18)
    profile, sketch = _make_rect_profile()
    bf = base_flange(profile=profile, sketch=sketch, config=cfg)
    assert math.isclose(bf.thickness.value, COLD_ROLLED_STEEL.thickness_for_gauge(18))
    assert math.isclose(
        bf.default_k_factor.value,
        COLD_ROLLED_STEEL.k_factor(cfg.bend_radius, cfg.thickness),
        abs_tol=1e-9,
    )


def test_base_flange_explicit_override():
    profile, sketch = _make_rect_profile()
    bf = base_flange(profile=profile, sketch=sketch, thickness=3.0, bend_radius=4.0, k_factor=0.43)
    assert bf.thickness.value == 3.0
    assert bf.default_bend_radius.value == 4.0
    assert bf.default_k_factor.value == 0.43
