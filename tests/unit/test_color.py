"""Unit tests for color resolution (named / hex / RGB) used by paint and materials."""

import math

import pytest

from cadbuildr.foundation.constants import DEFAULT_COLORS, resolve_color
from cadbuildr.foundation.gen.models import Material, MaterialOptions, Part, Sketch


def _approx(a, b):
    return all(math.isclose(x, y, abs_tol=1e-6) for x, y in zip(a, b))


def test_named_color_resolves():
    assert resolve_color("orange") == DEFAULT_COLORS["orange"]


def test_named_color_is_case_insensitive():
    assert resolve_color("Orange") == DEFAULT_COLORS["orange"]


def test_hex_color_full():
    # #212121 -> 0x21 == 33 -> 33/255
    assert _approx(resolve_color("#212121"), [33 / 255.0] * 3)


def test_hex_color_without_hash():
    assert _approx(resolve_color("212121"), [33 / 255.0] * 3)


def test_hex_color_shorthand():
    # #f00 -> ff,00,00
    assert _approx(resolve_color("#f00"), [1.0, 0.0, 0.0])


def test_rgb_list_unit_range_passthrough():
    assert _approx(resolve_color([0.1, 0.2, 0.3]), [0.1, 0.2, 0.3])


def test_rgb_list_255_range_normalized():
    assert _approx(resolve_color([255, 0, 128]), [1.0, 0.0, 128 / 255.0])


def test_unknown_color_raises_with_hint():
    with pytest.raises(ValueError) as exc:
        resolve_color("not-a-color")
    msg = str(exc.value)
    assert "hex" in msg and "orange" in msg


def test_wrong_length_rgb_raises():
    with pytest.raises(ValueError):
        resolve_color([0.1, 0.2])


def test_paint_accepts_hex():
    class _Cube(Part):
        def __init__(self):
            s = Sketch(self.xy())  # noqa: F841 (exercise a real Part lifecycle)
            self.paint("#212121")

    cube = _Cube()
    material = getattr(cube, "_material")
    assert _approx(material.options.diffuse_color, [33 / 255.0] * 3)


def test_set_diffuse_color_accepts_hex_and_rgb():
    m = Material(name="m", painted_node_ids=[], options=MaterialOptions(diffuse_color=[0, 0, 0]))
    m.set_diffuse_color("#00ff00")
    assert _approx(m.options.diffuse_color, [0.0, 1.0, 0.0])
    m.set_diffuse_color([255, 255, 255])
    assert _approx(m.options.diffuse_color, [1.0, 1.0, 1.0])
