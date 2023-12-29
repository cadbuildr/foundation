from foundation import *


class CircularTable:
    """Class for making a table with 1 center round leg and a circular top"""

    def __init__(
        self, leg_radius=0.25, top_radius=0.6, top_thickness=0.025, table_height=0.75
    ):
        self.leg_radius = leg_radius
        self.top_radius = top_radius
        self.top_thickness = top_thickness
        self.table_height = table_height

    def get_part(self):
        part = start_component()
        s = Sketch(part.origin_planes[0])
        p1 = Point(s, 0, 0)
        # outer extrusion
        circle = Circle(p1, self.top_radius)
        e = Extrusion(circle, self.top_thickness)
        # inside extrusion using cut
        circle2 = Circle(p1, self.leg_radius)
        e2 = Extrusion(circle2, self.table_height, cut=False)
        part.add_operation(e)
        part.add_operation(e2)
        return part


# show(CircularTable().get_part())
