from __future__ import annotations
from typing import Union
from .and_finder_rule import AndFinderRule
from .arc import Arc
from .assembly_root import AssemblyRoot
from .at_angle_finder_rule import AtAngleFinderRule
from .at_distance_finder_rule import AtDistanceFinderRule
from .chamfer import Chamfer
from .circle import Circle
from .contains_point_finder_rule import ContainsPointFinderRule
from .custom_closed_shape import CustomClosedShape
from .either_finder_rule import EitherFinderRule
from .ellipse import Ellipse
from .ellipse_arc import EllipseArc
from .extrusion import Extrusion
from .fillet import Fillet
from .hexagon import Hexagon
from .hole import Hole
from .in_box_finder_rule import InBoxFinderRule
from .in_direction_finder_rule import InDirectionFinderRule
from .in_plane_finder_rule import InPlaneFinderRule
from .lathe import Lathe
from .line import Line
from .loft import Loft
from .part_root import PartRoot
from .point import Point
from .polygon import Polygon
from .rectangle import Rectangle
from .rectangle_from2_points import RectangleFrom2Points
from .rectangle_from_center_and_sides import RectangleFromCenterAndSides
from .svg_shape import SVGShape
from .spline import Spline
from .square import Square
from .square_from_center_and_side import SquareFromCenterAndSide
from .sweep import Sweep
from .thread import Thread
BoundaryElement2D = Union[Line, Arc, EllipseArc, Spline]
ClosedShape2D = Union[Circle, Ellipse, Polygon, Hexagon, CustomClosedShape, SVGShape, Square, Rectangle, SquareFromCenterAndSide, RectangleFrom2Points, RectangleFromCenterAndSides]
Shape2D = Union[Circle, Ellipse, Polygon, CustomClosedShape, Square, Rectangle, SquareFromCenterAndSide, RectangleFrom2Points, RectangleFromCenterAndSides, Line, Arc, EllipseArc, Spline, Point]
SolidOperation = Union[Extrusion, Lathe]
FinderRule = Union[InPlaneFinderRule, AtAngleFinderRule, AtDistanceFinderRule, ContainsPointFinderRule, InBoxFinderRule, InDirectionFinderRule, AndFinderRule, EitherFinderRule]
Operation = Union[Extrusion, Hole, Lathe, Loft, Sweep, Thread, Fillet, Chamfer]
ComponentRoot = Union[PartRoot, AssemblyRoot]
