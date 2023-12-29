from foundation.std.hardware.screws_and_bolts.base import HexaBolt
from foundation import *
import numpy as np


bolt_head_diameter = 12
bolt_head_height = 6
bolt_diameter = 6
bolt_length = 60


class ExtruFeet:
    def __init__(self, diameter=40, height=30):
        self.diameter = diameter
        self.height = height

    def get_feet_operation(self):
        # Operation 1
        s = Sketch(self.component.origin_planes[0])

        p1 = Point(s, self.diameter, -(bolt_head_height + 2))
        p2 = Point(s, self.diameter / 2, self.height)
        p3 = Point(s, 0, self.height)
        p4 = Point(s, 0, -(bolt_head_height + 2))
        l1 = Line(p1, p2)
        l2 = Line(p2, p3)
        l3 = Line(p3, p4)
        l4 = Line(p4, p1)
        axis = Axis(Line(p4, p3))
        lines = [l1, l2, l3, l4]
        polygon = Polygon(s, [l1, l2, l3, l4])

        # Operation 2
        e = Lathe(polygon, axis)
        self.component.add_operation(e)

    def get_hexa_hole_operation(self):
        # Op 1 make hexa cut
        s = Sketch(self.component.origin_planes[1])
        self.center = Point(s, 0, 0)
        hexagon = Hexagon(self.center, (bolt_head_diameter + 2) / 2)
        # extrusion  cut
        e = Extrusion(hexagon, -(bolt_head_height + 2), cut=True)

        # op 2 make hole
        h = Hole(self.center, (bolt_diameter + 2) / 2, self.height)

        self.component.add_operation(e)
        self.component.add_operation(h)

    def get_part(self):
        self.component = start_component()
        self.get_feet_operation()
        self.get_hexa_hole_operation()
        m = Material()
        m.set_diffuse_color("orange")
        self.component.set_material(m)

        return self.component


class FeetAssy:
    def __init__(self):
        pass

    def get_assy(self):
        assembly = start_assembly()
        bolt = HexaBolt(length=bolt_length).get_part()
        feet = ExtruFeet().get_part()

        bolt_tf = TFHelper().rotate(axis=[1, 0, 0], angle=-np.pi / 2).get_tf()

        m = Material()
        m.set_diffuse_color("orange")
        feet.set_material(m)

        assembly.add_component(bolt, bolt_tf)
        assembly.add_component(feet)

        top_assembly = start_assembly()
        top_assembly.add_component(
            assembly, TFHelper().rotate(axis=[1, 0, 0], angle=-np.pi / 2).get_tf()
        )

        return top_assembly


# show(FeetAssy().get_assy())
