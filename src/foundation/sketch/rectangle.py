import math
from foundation.sketch.primitives.line import Line
from foundation.sketch.point import Point
from foundation.sketch.closed_sketch_shape import Polygon, RoundedCornerPolygon

from typing import TYPE_CHECKING, Type, Union

if TYPE_CHECKING:
    from foundation.sketch.sketch import Sketch


class BaseRectangle:
    def __init__(self, sketch: "Sketch", p1: Point, p2: Point, p3: Point, p4: Point):
        self.sketch = sketch
        self.p1 = p1
        self.p2 = p2
        self.p3 = p3
        self.p4 = p4
        self.lines = [Line(p1, p2), Line(p2, p3), Line(p3, p4), Line(p4, p1)]

    @classmethod
    def from_2_points(
        cls: Type["BaseRectangle"], p1: Point, p3: Point, radius: float | None = None
    ) -> Union["Rectangle", "RoundedCornerRectangle"]:
        sketch = p1.sketch
        p2 = Point(sketch, p3.x.value, p1.y.value)
        p4 = Point(sketch, p1.x.value, p3.y.value)
        return cls.create_rectangle(sketch, p1, p2, p3, p4, radius)

    @classmethod
    def from_center_and_point(
        cls: Type["BaseRectangle"],
        center: Point,
        p1: Point,
        radius: float | None = None,
    ) -> Union["Rectangle", "RoundedCornerRectangle"]:
        sketch = center.sketch
        dx = center.x.value - p1.x.value
        dy = center.y.value - p1.y.value

        p2 = Point(sketch, p1.x.value, p1.y.value + dy * 2)
        p3 = Point(sketch, p1.x.value + dx * 2, p1.y.value + dy * 2)
        p4 = Point(sketch, p1.x.value + dx * 2, p1.y.value)

        return cls.create_rectangle(sketch, p1, p2, p3, p4, radius)

    @classmethod
    def from_3_points(
        cls: Type["BaseRectangle"],
        p1: Point,
        p2: Point,
        opposed: Point,
        radius: float | None = None,
    ) -> Union["Rectangle", "RoundedCornerRectangle"]:
        sketch = p1.sketch
        l1 = Line(p1, p2)
        width = l1.distance_to_point(opposed, absolute=False)
        angle = math.atan2(l1.dy(), l1.dx())

        p3 = Point(
            sketch,
            p2.x.value + width * math.cos(angle),
            p2.y.value + width * math.sin(angle),
        )
        p4 = Point(
            sketch,
            p1.x.value + width * math.cos(angle),
            p1.y.value + width * math.sin(angle),
        )

        return cls.create_rectangle(sketch, p1, p2, p3, p4, radius)

    @classmethod
    def from_center_and_sides(
        cls: Type["BaseRectangle"],
        center: Point,
        length: float,
        width: float,
        radius: float | None = None,
    ) -> Union["Rectangle", "RoundedCornerRectangle"]:
        sketch = center.sketch
        p1 = Point(sketch, center.x.value - length / 2, center.y.value - width / 2)
        p4 = Point(sketch, center.x.value - length / 2, center.y.value + width / 2)
        p3 = Point(sketch, center.x.value + length / 2, center.y.value + width / 2)
        p2 = Point(sketch, center.x.value + length / 2, center.y.value - width / 2)

        return cls.create_rectangle(sketch, p1, p2, p3, p4, radius)

    @classmethod
    def create_rectangle(
        cls: Type["BaseRectangle"],
        sketch: "Sketch",
        p1: Point,
        p2: Point,
        p3: Point,
        p4: Point,
        radius: float | None,
    ) -> Union["Rectangle", "RoundedCornerRectangle"]:
        if radius is not None:
            return RoundedCornerRectangle(sketch, p1, p2, p3, p4, radius)
        else:
            return Rectangle(sketch, p1, p2, p3, p4)


class Rectangle(Polygon, BaseRectangle):
    def __init__(self, sketch: "Sketch", p1: Point, p2: Point, p3: Point, p4: Point):
        BaseRectangle.__init__(self, sketch, p1, p2, p3, p4)
        Polygon.__init__(self, sketch, self.lines)


class Square(Rectangle):
    def __init__(self, sketch: "Sketch", p1: Point, p2: Point, p3: Point, p4: Point):
        super().__init__(sketch, p1, p2, p3, p4)

    @staticmethod
    def from_center_and_side(center: Point, size: float) -> "Square":
        sketch = center.sketch
        rect = BaseRectangle.from_center_and_sides(center, size, size)
        return Square(rect.sketch, rect.p1, rect.p2, rect.p3, rect.p4)


class RoundedCornerRectangle(RoundedCornerPolygon, BaseRectangle):
    def __init__(
        self,
        sketch: "Sketch",
        p1: Point,
        p2: Point,
        p3: Point,
        p4: Point,
        radius: float,
    ):
        BaseRectangle.__init__(self, sketch, p1, p2, p3, p4)
        RoundedCornerPolygon.__init__(self, sketch, self.lines, radius)


class RoundedCornerSquare(RoundedCornerRectangle):
    def __init__(
        self,
        sketch: "Sketch",
        p1: Point,
        p2: Point,
        p3: Point,
        p4: Point,
        radius: float,
    ):
        super().__init__(sketch, p1, p2, p3, p4, radius)

    @staticmethod
    def from_center_and_side(
        center: Point, size: float, radius: float
    ) -> "RoundedCornerSquare":
        sketch = center.sketch
        rect = BaseRectangle.from_center_and_sides(center, size, size, radius)
        return RoundedCornerSquare(
            rect.sketch, rect.p1, rect.p2, rect.p3, rect.p4, radius
        )
