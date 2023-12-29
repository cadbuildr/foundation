from foundation.gcs.constraints.base import FoundationConstraint2D
from foundation.types.node import Node
from foundation.sketch.point import Point
from foundation.sketch.line import Line


class PointDistanceToOriginConstraint(FoundationConstraint2D, Node):
    parent_types = [Point, float]  # TODO check types ?

    def __init__(self, point: Point, distance: float):
        FoundationConstraint2D.__init__(self, primitives=[point], params=[distance])
        Node.__init__(self, parents=[point, distance])
        self._point = point
        self._distance = distance


class PointAnchoring2D(FoundationConstraint2D):
    parent_types = [Point, bool, bool]

    def __init__(self, point: Point, anchor_x: bool = True, anchor_y: bool = True):
        FoundationConstraint2D.__init__(
            self, primitives=[point], params=[point.x.value, point.y.value]
        )
        Node.__init__(self, parents=[point, anchor_x, anchor_y])

        self._point = point
        self._anchor_x = anchor_x
        self._anchor_y = anchor_y


class LineLengthConstraint(FoundationConstraint2D):
    parent_types = [Line, float]

    def __init__(self, line: Line, dist: float):
        """line and Distance primitive"""
        FoundationConstraint2D.__init__(self, primitives=[line], params=[dist])
        Node.__init__(self, parents=[line, dist])
        self._line = line
        self._dist = dist


class ThreePointsAlignedConstraint(FoundationConstraint2D):
    parent_types = [Point, Point, Point]

    def __init__(self, p1: Point, p2: Point, p3: Point):
        """Three points aligned"""
        FoundationConstraint2D.__init__(self, primitives=[p1, p2, p3], params=[])
        Node.__init__(self, parents=[p1, p2, p3])
        self._p1 = p1
        self._p2 = p2
        self._p3 = p3


class PointDistanceToLineConstraint(FoundationConstraint2D):
    parent_types = [Point, Line, float]

    def __init__(self, point: Point, line: Line, dist: float):
        """Point and line and Distance primitive"""
        FoundationConstraint2D.__init__(self, primitives=[point, line], params=[dist])
        Node.__init__(self, parents=[point, line, dist])
        self._point = point
        self._line = line
        self._dist = dist


class SameLengthConstraint(FoundationConstraint2D):
    parent_types = [Line, Line]

    def __init__(self, line1: Line, line2: Line):
        """Two lines with same length"""
        FoundationConstraint2D.__init__(self, primitives=[line1, line2], params=[])
        Node.__init__(self, parents=[line1, line2])
        self._line1 = line1
        self._line2 = line2


class PointToPointDistanceConstraint(FoundationConstraint2D):
    parent_types = [Point, Point, float]

    def __init__(self, p1: Point, p2: Point, dist: float):
        """Two points with same distance"""
        FoundationConstraint2D.__init__(self, primitives=[p1, p2], params=[dist])
        Node.__init__(self, parents=[p1, p2, dist])
        self._p1 = p1
        self._p2 = p2
        self._dist = dist


class ThreePointsAngleConstraint(FoundationConstraint2D):
    parent_types = [Point, Point, Point, float]

    def __init__(self, p1: Point, p2: Point, p3: Point, angle: float):
        """Three points with same angle"""
        FoundationConstraint2D.__init__(self, primitives=[p1, p2, p3], params=[angle])
        Node.__init__(self, parents=[p1, p2, p3, angle])
        self._p1 = p1
        self._p2 = p2
        self._p3 = p3
        self._angle = angle


class LineAngularConstraint(FoundationConstraint2D):
    parent_types = [Line, Line, float]

    def __init__(self, line1: Line, line2: Line, angle: float):
        """Two lines with same angle"""
        FoundationConstraint2D.__init__(self, primitives=[line1, line2], params=[angle])
        Node.__init__(self, parents=[line1, line2, angle])
        self._line1 = line1
        self._line2 = line2
        self._angle = angle


class ColinearConstraint(FoundationConstraint2D):
    parent_types = [Line, Line]

    def __init__(self, line1: Line, line2: Line):
        """Two lines colinear"""
        FoundationConstraint2D.__init__(self, primitives=[line1, line2], params=[])
        Node.__init__(self, parents=[line1, line2])
        self._line1 = line1
        self._line2 = line2


class HorizontalConstraint(FoundationConstraint2D):
    parent_types = [Line]

    def __init__(self, line: Line):
        """Line horizontal"""
        FoundationConstraint2D.__init__(self, primitives=[line], params=[])
        Node.__init__(self, parents=[line])
        self._line = line


class VerticalConstraint(FoundationConstraint2D):
    parent_types = [Line]

    def __init__(self, line: Line):
        """Line vertical"""
        FoundationConstraint2D.__init__(self, primitives=[line], params=[])
        Node.__init__(self, parents=[line])
        self._line = line
