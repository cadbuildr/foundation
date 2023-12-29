from foundation import *


class Screw:
    """Base class for screws and bolts to inherit from
    # TODO add thread
    # TODO go through catalog and add all screws and bolts
    """

    def __init__(self, length, diameter, head_type, head_height, head_diameter):
        self.length = length
        self.diameter = diameter
        self.head_type = head_type
        self.head_height = head_height
        self.head_diameter = head_diameter

    def get_head_operation(self):
        raise NotImplementedError("Implement in children")

    def get_main_cylinder_operation(self):
        raise NotImplementedError("Implement in children")

    def get_part(self):
        self.component = start_component()
        self.s = Sketch(self.component.origin_planes[0])
        self.center = self.s.origin

        # Create the head
        head_operation = self.get_head_operation()
        self.component.add_operation(head_operation)

        # Create the main cylinder
        main_cylinder_operation = self.get_main_cylinder_operation()
        self.component.add_operation(main_cylinder_operation)

        return self.component


class HexaBolt(Screw):
    """A bolt with a hexagonal head"""

    def __init__(self, length=12, diameter=6, head_height=6, head_diameter=12):
        self.length = length
        self.diameter = diameter
        self.head_height = head_height
        self.head_diameter = head_diameter

    def get_head_operation(self):
        hexagon = Hexagon(self.center, self.head_diameter / 2)
        return Extrusion(hexagon, self.head_height)

    def get_main_cylinder_operation(self):
        circle = Circle(self.center, self.diameter / 2)
        return Extrusion(circle, -self.length)
