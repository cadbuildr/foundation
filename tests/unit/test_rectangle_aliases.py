from cadbuildr.foundation import Rectangle  # pragma: allowlist secret
from cadbuildr.foundation.gen.models import Part, Sketch  # pragma: allowlist secret


def test_rectangle_aliases_match_existing_factories():
    part = Part()
    sketch = Sketch(part.xy())

    # Keep both legacy and new names equivalent for model-generated code.
    rect_from_points = Rectangle.from_2_points(
        sketch.origin.translate(-10, -5), sketch.origin.translate(10, 5)
    )
    rect_from_corners = Rectangle.from_2_corners(
        sketch.origin.translate(-10, -5), sketch.origin.translate(10, 5)
    )

    assert rect_from_points is not None
    assert rect_from_corners is not None
    assert rect_from_points.p1.x.value == rect_from_corners.p1.x.value
    assert rect_from_points.p1.y.value == rect_from_corners.p1.y.value
    assert rect_from_points.p3.x.value == rect_from_corners.p3.x.value
    assert rect_from_points.p3.y.value == rect_from_corners.p3.y.value


def test_rectangle_center_sides_accepts_origin_w_h():
    part = Part()
    sketch = Sketch(part.xy())

    rect = Rectangle.from_center_and_sides(sketch.origin, 40, 20)
    assert rect is not None
    assert rect.p1.x.value == -20
    assert rect.p1.y.value == -10
    assert rect.p3.x.value == 20
    assert rect.p3.y.value == 10
