from foundation.gcs.constraints.constraints2d import (
    LineLengthConstraint,
    SameLengthConstraint,
    PointToPointDistanceConstraint,
    PointDistanceToOriginConstraint,
    PointAnchoring2D,
    ThreePointsAngleConstraint,
    PointDistanceToLineConstraint,
    ThreePointsAlignedConstraint,
    ColinearConstraint,
    HorizontalConstraint,
    VerticalConstraint,
)

from typing import List
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from foundation.sketch.base import Line, Point
    from foundation.sketch.sketch import Sketch

import numpy as np


class ConstraintsFactory:
    """Class to create all sort of constraints ( in a sketch),
    meant to be a wrapper around the low level constraints to make it easy to use.
    """

    def __init__(self, sketch: "Sketch"):
        self.sketch = sketch

    def length(self, line: "Line", length: float):
        c = LineLengthConstraint(line, length)
        self.sketch.add_constraint(c)

    def p2p_dist(self, p1: "Point", p2: "Point", dist: float):
        c = PointToPointDistanceConstraint(p1, p2, dist)
        self.sketch.add_constraint(c)

    def p2origin_dist(self, p: "Point", dist: float):
        c = PointDistanceToOriginConstraint(p, dist)
        self.sketch.add_constraint(c)

    def p2line_dist(self, p: "Point", l: "Line", dist: float):
        """Could be negative distance to be on the other side of the line."""
        c = PointDistanceToLineConstraint(p, l, dist)
        self.sketch.add_constraint(c)

    def same_length(self, lines: List["Line"]):
        """Create a constraint to ensure that all lines have the same length"""
        c = SameLengthConstraint(lines)
        self.sketch.add_constraint(c)

    def perpendicular(self, l1: "Line", l2: "Line"):
        # TODO
        raise NotImplementedError("Not implemented yet")

    def horizontal(self, l1: "Line"):
        c = HorizontalConstraint(l1)
        self.sketch.add_constraint(c)

    def vertical(self, l: "Line"):
        c = VerticalConstraint(l)
        self.sketch.add_constraint(c)

    def colinear(self, l1: "Line", l2: "Line"):
        c = ColinearConstraint(l1, l2)
        self.sketch.add_constraint(c)

    def three_point_angle(self, p1: "Point", p2: "Point", p3: "Point", angle: float):
        """Angle between P1P2 and P1P3"""
        c = ThreePointsAngleConstraint(p1, p2, p3, angle)
        self.sketch.add_constraint(c)

    def three_point_right_angle(self, p1: "Point", p2: "Point", p3: "Point"):
        """Right Angle between P1P2 and P1P3"""
        c = ThreePointsAngleConstraint(p1, p2, p3, np.pi / 2)
        self.sketch.add_constraint(c)

    def aligned(self, p1: "Point", p2: "Point", p3: "Point"):
        """Aligned with P1P2 and P1P3"""
        c = ThreePointsAlignedConstraint(p1, p2, p3)
        self.sketch.add_constraint(c)

    def anchor_point(self, p: "Point"):
        c = PointAnchoring2D(p)
        self.sketch.add_constraint(c)

    def anchor_point_x(self, p: "Point"):
        c = PointAnchoring2D(p, anchor_y=False)
        self.sketch.add_constraint(c)

    def anchor_point_y(self, p: "Point"):
        c = PointAnchoring2D(p, anchor_x=False)
        self.sketch.add_constraint(c)
