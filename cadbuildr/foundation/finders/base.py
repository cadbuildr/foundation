from cadbuildr.foundation.types.node_children import NodeChildren
from cadbuildr.foundation.types.node import Node
from cadbuildr.foundation.types.node_interface import NodeInterface

from cadbuildr.foundation.types.parameters import (
    UnCastFloat,
    cast_to_float_parameter,
    FloatParameter,
)
from cadbuildr.foundation.types.types_3d.point_3d import Point3D
from cadbuildr.foundation.geometry.plane import Plane


class FinderRule(NodeInterface):
    """Base class for Finderrules"""

    pass


class InPlaneFinderRuleChildren(NodeChildren):
    plane: Plane  # Plane in which to do the search
    distance: FloatParameter  # distance to plane if needed (default to 0)


class InPlaneFinderRule(FinderRule, Node):
    children_class = InPlaneFinderRuleChildren

    def __init__(self, plane: Plane, distance: UnCastFloat = 0.0):
        FinderRule.__init__(self)
        Node.__init__(self, parents=[])
        self.children.set_plane(plane)
        self.children.set_distance(cast_to_float_parameter(distance))
        self.plane = self.children.plane
        self.distance = self.children.distance
        self.params = {}


InPlaneFinderRuleChildren.__annotations__["plane"] = Plane
InPlaneFinderRuleChildren.__annotations__["distance"] = FloatParameter


class AtAngleFinderRuleChildren(NodeChildren):
    angle: FloatParameter  # angle in radians
    direction: Point3D  # direction of the angle


class AtAngleFinderRule(FinderRule, Node):
    children_class = AtAngleFinderRuleChildren

    def __init__(self, angle: UnCastFloat, direction: Point3D):
        FinderRule.__init__(self)
        Node.__init__(self, parents=[])
        self.children.set_angle(cast_to_float_parameter(angle))
        self.children.set_direction(direction)
        self.angle = self.children.angle
        self.direction = self.children.direction
        self.params = {}


AtAngleFinderRuleChildren.__annotations__["angle"] = FloatParameter
AtAngleFinderRuleChildren.__annotations__["direction"] = Point3D


class AtDistanceFinderRuleChildren(NodeChildren):
    distance: FloatParameter  # distance to the object
    point: Point3D  # point to measure distance from


class AtDistanceFinderRule(FinderRule, Node):
    children_class = AtDistanceFinderRuleChildren

    def __init__(self, distance: UnCastFloat, point: Point3D):
        FinderRule.__init__(self)
        Node.__init__(self, parents=[])
        self.children.set_distance(cast_to_float_parameter(distance))
        self.children.set_point(point)
        self.distance = self.children.distance
        self.point = self.children.point
        self.params = {}


AtDistanceFinderRuleChildren.__annotations__["distance"] = FloatParameter
AtDistanceFinderRuleChildren.__annotations__["point"] = Point3D


class ContainsPointFinderRuleChildren(NodeChildren):
    point: Point3D  # point to check if it is contained


class ContainsPointFinderRule(FinderRule, Node):
    children_class = ContainsPointFinderRuleChildren

    def __init__(self, point: Point3D):
        FinderRule.__init__(self)
        Node.__init__(self, parents=[])
        self.children.set_point(point)
        self.point = self.children.point
        self.params = {}


ContainsPointFinderRuleChildren.__annotations__["point"] = Point3D


class InBoxFinderRuleChildren(NodeChildren):
    corner1: Point3D  # corner 1 of the box
    corner2: Point3D  # corner 2 of the box


class InBoxFinderRule(FinderRule, Node):
    children_class = InBoxFinderRuleChildren

    def __init__(self, corner1: Point3D, corner2: Point3D):
        FinderRule.__init__(self)
        Node.__init__(self, parents=[])
        self.children.set_corner1(corner1)
        self.children.set_corner2(corner2)
        self.corner1 = self.children.corner1
        self.corner2 = self.children.corner2
        self.params = {}


InBoxFinderRuleChildren.__annotations__["corner1"] = Point3D
InBoxFinderRuleChildren.__annotations__["corner2"] = Point3D


class InDirectionFinderRuleChildren(NodeChildren):
    direction: Point3D  # direction to search in


class InDirectionFinderRule(FinderRule, Node):
    children_class = InDirectionFinderRuleChildren

    def __init__(self, direction: Point3D):
        FinderRule.__init__(self)
        Node.__init__(self, parents=[])
        self.children.set_direction(direction)
        self.direction = self.children.direction
        self.params = {}


InDirectionFinderRuleChildren.__annotations__["direction"] = Point3D


class AndFinderRuleChildren(NodeChildren):
    rules: list[FinderRule]  # list of rules to be combined with AND


class AndFinderRule(FinderRule, Node):
    children_class = AndFinderRuleChildren

    def __init__(self, rules: list[FinderRule]):
        FinderRule.__init__(self)
        Node.__init__(self, parents=[])
        self.children.set_rules(rules)
        self.rules = self.children.rules
        self.params = {}


AndFinderRuleChildren.__annotations__["rules"] = list[FinderRule]


class EitherFinderRuleChildren(NodeChildren):
    rules: list[FinderRule]  # list of rules to be combined with OR


class EitherFinderRule(FinderRule, Node):
    children_class = EitherFinderRuleChildren

    def __init__(self, rules: list[FinderRule]):
        FinderRule.__init__(self)
        Node.__init__(self, parents=[])
        self.children.set_rules(rules)
        self.rules = self.children.rules
        self.params = {}


EitherFinderRuleChildren.__annotations__["rules"] = list[FinderRule]


FinderRuleTypes = (
    InPlaneFinderRule
    | AtAngleFinderRule
    | AtDistanceFinderRule
    | ContainsPointFinderRule
    | InBoxFinderRule
    | InDirectionFinderRule
    | AndFinderRule
    | EitherFinderRule
)


class EdgeFinderChildren(NodeChildren):
    rule: FinderRuleTypes


class EdgeFinder(Node):
    children_class = EdgeFinderChildren

    def __init__(self, rule: FinderRuleTypes):
        Node.__init__(self, parents=[])
        self.children.set_rule(rule)
        self.rule = self.children.rule


EdgeFinderChildren.__annotations__["rule"] = FinderRuleTypes


class FaceFinderChildren(NodeChildren):
    rule: FinderRuleTypes


class FaceFinder(Node):
    children_class = FaceFinderChildren

    def __init__(self, rule: FinderRuleTypes):
        Node.__init__(self, parents=[])
        self.children.set_rule(rule)
        self.rule = self.children.rule


FaceFinderChildren.__annotations__["rule"] = FinderRuleTypes
