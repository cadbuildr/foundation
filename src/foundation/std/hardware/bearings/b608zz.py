from foundation import *

# Class for making 608zz bearings and other standard bearings

bearing_dimensions = {
    "608zz": {"d": 8, "D": 22, "L": 7},
    "623zz": {"d": 3, "D": 10, "L": 4},
    "624zz": {"d": 4, "D": 13, "L": 5},
    "625zz": {"d": 5, "D": 16, "L": 5},
    "626zz": {"d": 6, "D": 19, "L": 6},
    "688zz": {"d": 8, "D": 16, "L": 5},
    "635zz": {"d": 5, "D": 19, "L": 6},
}


class Bearing:
    def __init__(self, modelNo="608zz"):
        self.modelNo = modelNo
        self.d = bearing_dimensions[modelNo]["d"]
        self.D = bearing_dimensions[modelNo]["D"]
        self.L = bearing_dimensions[modelNo]["L"]

    def get_part(self):
        part = start_component()
        s = Sketch(part.origin_planes[0])
        p1 = Point(s, 0, 0)
        # outer extrusion
        circle = Circle(p1, self.D / 2)
        e = Extrusion(circle, self.L)
        # inside extrusion using cut
        circle2 = Circle(p1, self.d / 2)
        e2 = Extrusion(circle2, self.L, cut=True)
        part.add_operation(e)
        part.add_operation(e2)
        return part
