"""Generated GraphQL types for foundation."""

from __future__ import annotations
from .float_parameter import FloatParameter
from .int_parameter import IntParameter
from .bool_parameter import BoolParameter
from .string_parameter import StringParameter
from .point import Point
from .line import Line
from .arc import Arc
from .spline import Spline
from .arc_from_two_points_and_radius import ArcFromTwoPointsAndRadius
from .circle import Circle
from .ellipse import Ellipse
from .ellipse_arc import EllipseArc
from .polygon import Polygon
from .hexagon import Hexagon
from .custom_closed_shape import CustomClosedShape
from .svg_shape import SVGShape
from .rectangle import Rectangle
from .square import Square
from .square_from_center_and_side import SquareFromCenterAndSide
from .rectangle_from2_points import RectangleFrom2Points
from .rectangle_from_center_and_sides import RectangleFromCenterAndSides
from .frame import Frame
from .plane import Plane
from .point3_d import Point3D
from .helix3_d import Helix3D
from .sketch import Sketch
from .extrusion import Extrusion
from .hole import Hole
from .axis import Axis
from .lathe import Lathe
from .loft import Loft
from .sweep import Sweep
from .thread import Thread
from .in_plane_finder_rule import InPlaneFinderRule
from .at_angle_finder_rule import AtAngleFinderRule
from .at_distance_finder_rule import AtDistanceFinderRule
from .contains_point_finder_rule import ContainsPointFinderRule
from .in_box_finder_rule import InBoxFinderRule
from .in_direction_finder_rule import InDirectionFinderRule
from .and_finder_rule import AndFinderRule
from .either_finder_rule import EitherFinderRule
from .edge_finder import EdgeFinder
from .fillet import Fillet
from .chamfer import Chamfer
from .material_options import MaterialOptions
from .material import Material
from .fixed_translation_constraint import FixedTranslationConstraint
from .interface_grid_spec import InterfaceGridSpec
from .assembly_interface import AssemblyInterface
from .part import Part
from .part_root import PartRoot
from .assembly import Assembly
from .assembly_root import AssemblyRoot
from .unions import (
    BoundaryElement2D,
    ClosedShape2D,
    Shape2D,
    SolidOperation,
    FinderRule,
    Operation,
    ComponentRoot
)
FloatParameter.model_rebuild()

IntParameter.model_rebuild()

BoolParameter.model_rebuild()

StringParameter.model_rebuild()

Point.model_rebuild()

Line.model_rebuild()

Arc.model_rebuild()

Spline.model_rebuild()

ArcFromTwoPointsAndRadius.model_rebuild()

Circle.model_rebuild()

Ellipse.model_rebuild()

EllipseArc.model_rebuild()

Polygon.model_rebuild()

Hexagon.model_rebuild()

CustomClosedShape.model_rebuild()

SVGShape.model_rebuild()

Rectangle.model_rebuild()

Square.model_rebuild()

SquareFromCenterAndSide.model_rebuild()

RectangleFrom2Points.model_rebuild()

RectangleFromCenterAndSides.model_rebuild()

Frame.model_rebuild()

Plane.model_rebuild()

Point3D.model_rebuild()

Helix3D.model_rebuild()

Sketch.model_rebuild()

Extrusion.model_rebuild()

Hole.model_rebuild()

Axis.model_rebuild()

Lathe.model_rebuild()

Loft.model_rebuild()

Sweep.model_rebuild()

Thread.model_rebuild()

InPlaneFinderRule.model_rebuild()

AtAngleFinderRule.model_rebuild()

AtDistanceFinderRule.model_rebuild()

ContainsPointFinderRule.model_rebuild()

InBoxFinderRule.model_rebuild()

InDirectionFinderRule.model_rebuild()

AndFinderRule.model_rebuild()

EitherFinderRule.model_rebuild()

EdgeFinder.model_rebuild()

Fillet.model_rebuild()

Chamfer.model_rebuild()

MaterialOptions.model_rebuild()

Material.model_rebuild()

FixedTranslationConstraint.model_rebuild()

InterfaceGridSpec.model_rebuild()

AssemblyInterface.model_rebuild()

Part.model_rebuild()

PartRoot.model_rebuild()

Assembly.model_rebuild()

AssemblyRoot.model_rebuild()

from ..runtime import register_type
register_type("EllipseArc", EllipseArc)
register_type("InterfaceGridSpec", InterfaceGridSpec)

register_type("Arc", Arc)

register_type("Material", Material)

register_type("Frame", Frame)

register_type("SVGShape", SVGShape)

register_type("Extrusion", Extrusion)

register_type("Helix3D", Helix3D)

register_type("Plane", Plane)

register_type("Hole", Hole)

register_type("InPlaneFinderRule", InPlaneFinderRule)

register_type("Assembly", Assembly)

register_type("Part", Part)

register_type("Thread", Thread)

register_type("AssemblyInterface", AssemblyInterface)

register_type("Lathe", Lathe)

register_type("Hexagon", Hexagon)

register_type("Square", Square)

register_type("Rectangle", Rectangle)

register_type("SquareFromCenterAndSide", SquareFromCenterAndSide)

register_type("RectangleFrom2Points", RectangleFrom2Points)

register_type("RectangleFromCenterAndSides", RectangleFromCenterAndSides)
try:
    from ... import compute_functions  # noqa: F401
except ImportError:
    # compute_functions may not exist in all packages
    pass


__all__ = [
    "FloatParameter",
    "IntParameter",
    "BoolParameter",
    "StringParameter",
    "Point",
    "Line",
    "Arc",
    "Spline",
    "ArcFromTwoPointsAndRadius",
    "Circle",
    "Ellipse",
    "EllipseArc",
    "Polygon",
    "Hexagon",
    "CustomClosedShape",
    "SVGShape",
    "Rectangle",
    "Square",
    "SquareFromCenterAndSide",
    "RectangleFrom2Points",
    "RectangleFromCenterAndSides",
    "Frame",
    "Plane",
    "Point3D",
    "Helix3D",
    "Sketch",
    "Extrusion",
    "Hole",
    "Axis",
    "Lathe",
    "Loft",
    "Sweep",
    "Thread",
    "InPlaneFinderRule",
    "AtAngleFinderRule",
    "AtDistanceFinderRule",
    "ContainsPointFinderRule",
    "InBoxFinderRule",
    "InDirectionFinderRule",
    "AndFinderRule",
    "EitherFinderRule",
    "EdgeFinder",
    "Fillet",
    "Chamfer",
    "MaterialOptions",
    "Material",
    "FixedTranslationConstraint",
    "InterfaceGridSpec",
    "AssemblyInterface",
    "Part",
    "PartRoot",
    "Assembly",
    "AssemblyRoot",
    "BoundaryElement2D",
    "ClosedShape2D",
    "Shape2D",
    "SolidOperation",
    "FinderRule",
    "Operation",
    "ComponentRoot",
]
