from __future__ import annotations

import math
from cadbuildr.foundation.sketch.primitives.line import Line
from cadbuildr.foundation.sketch.point import Point
from cadbuildr.foundation.sketch.closed_sketch_shape import (
    Polygon,
    RoundedCornerPolygon,
)
from cadbuildr.foundation.exceptions import ElementsNotOnSameSketchException

from typing import Type, TypeVar

TOLERANCE = 1e-6  # TODO find a place for this type of things

T = TypeVar("T", bound="BaseRectangle")


class BaseRectangle:
    def __init__(self, p1: Point, p2: Point, p3: Point, p4: Point):
        if p1.sketch != p2.sketch or p1.sketch != p3.sketch or p1.sketch != p4.sketch:
            raise ElementsNotOnSameSketchException(
                f"Points {p1}, {p2}, {p3}, {p4} are not on the same sketch"
            )
        sketch = p1.sketch

        self.sketch = sketch
        self.p1 = p1
        self.p2 = p2
        self.p3 = p3
        self.p4 = p4
        self.lines = [Line(p1, p2), Line(p2, p3), Line(p3, p4), Line(p4, p1)]

    @classmethod
    def from_2_points(
        cls: Type[T], p1: Point, p3: Point, radius: float | None = None
    ) -> T:
        sketch = p1.sketch
        p2 = Point(sketch, p3.x.value, p1.y.value)
        p4 = Point(sketch, p1.x.value, p3.y.value)
        return cls.create_rectangle(p1, p2, p3, p4, radius)

    @classmethod
    def from_center_and_point(
        cls: Type[T],
        center: Point,
        p1: Point,
        radius: float | None = None,
    ) -> T:
        if center.sketch != p1.sketch:
            raise ElementsNotOnSameSketchException(
                f"Points {center} and {p1} are not on the same sketch"
            )
        sketch = p1.sketch
        dx = center.x.value - p1.x.value
        dy = center.y.value - p1.y.value

        p2 = Point(sketch, p1.x.value, p1.y.value + dy * 2)
        p3 = Point(sketch, p1.x.value + dx * 2, p1.y.value + dy * 2)
        p4 = Point(sketch, p1.x.value + dx * 2, p1.y.value)

        return cls.create_rectangle(p1, p2, p3, p4, radius)

    @classmethod
    def from_3_points(
        cls: Type[T],
        p1: Point,
        p2: Point,
        opposed: Point,
        radius: float | None = None,
    ) -> T:

        l1 = Line(p1, p2)
        width = l1.distance_to_point(opposed, absolute=False)
        angle = math.atan2(l1.dy(), l1.dx())

        sketch = p1.sketch
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

        return cls.create_rectangle(p1, p2, p3, p4, radius)

    @classmethod
    def from_center_and_sides(
        cls: Type[T],
        center: Point,
        length: float,
        width: float,
        radius: float | None = None,
    ) -> T:
        sketch = center.sketch
        if abs(length) < TOLERANCE:
            raise ValueError("Rectangle length cannot be zero or near-zero")
        if abs(width) < TOLERANCE:
            raise ValueError("Rectangle width cannot be zero or near-zero")
        if radius is not None and abs(radius) < TOLERANCE:
            raise ValueError("Rectangle corner radius cannot be zero or near-zero")
        p1 = Point(sketch, center.x.value - length / 2, center.y.value - width / 2)
        p4 = Point(sketch, center.x.value - length / 2, center.y.value + width / 2)
        p3 = Point(sketch, center.x.value + length / 2, center.y.value + width / 2)
        p2 = Point(sketch, center.x.value + length / 2, center.y.value - width / 2)

        return cls.create_rectangle(p1, p2, p3, p4, radius)

    @classmethod
    def create_rectangle(
        cls: Type[T],
        p1: Point,
        p2: Point,
        p3: Point,
        p4: Point,
        radius: float | None,
    ) -> T:
        if radius is not None and issubclass(cls, RoundedCornerRectangle):
            return cls(p1, p2, p3, p4, radius)  # type: ignore
        elif issubclass(cls, Rectangle):
            return cls(p1, p2, p3, p4)  # type: ignore
        else:
            raise TypeError(f"Unsupported class type: {cls}")


class Rectangle(Polygon, BaseRectangle):
    def __init__(self, p1: Point, p2: Point, p3: Point, p4: Point):
        BaseRectangle.__init__(self, p1, p2, p3, p4)
        Polygon.__init__(self, self.lines)


class Square(Rectangle):
    def __init__(self, p1: Point, p2: Point, p3: Point, p4: Point):
        super().__init__(p1, p2, p3, p4)

    @classmethod
    def from_center_and_side(cls: Type[T], center: Point, size: float) -> T:
        if abs(size) < TOLERANCE:
            raise ValueError("Rectangle size cannot be zero or near-zero")
        return cls.from_center_and_sides(center, size, size)


class RoundedCornerRectangle(RoundedCornerPolygon, BaseRectangle):
    def __init__(
        self,
        p1: Point,
        p2: Point,
        p3: Point,
        p4: Point,
        radius: float,
    ):
        BaseRectangle.__init__(self, p1, p2, p3, p4)
        RoundedCornerPolygon.__init__(self, self.lines, radius)


class RoundedCornerSquare(RoundedCornerRectangle):
    def __init__(
        self,
        p1: Point,
        p2: Point,
        p3: Point,
        p4: Point,
        radius: float,
    ):
        super().__init__(p1, p2, p3, p4, radius)

    @classmethod
    def from_center_and_side(
        cls: Type[RoundedCornerSquare], center: Point, size: float, radius: float
    ) -> RoundedCornerSquare:
        rect = BaseRectangle.from_center_and_sides(center, size, size, radius)
        return cls(rect.p1, rect.p2, rect.p3, rect.p4, radius)
