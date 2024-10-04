# File for Parametric Axis Holder SK-size
# TODO make part of a repo.

from foundation import *

# dimensions in mm
model_params = {
    "SK8": {
        "shaft": 8,
        "h": 20,
        "E": 21,
        "W": 42,
        "L": 14,
        "F": 32.8,
        "G": 6,
        "P": 18,
        "B": 32,
        "S": 5.5,
        "LB": 4,
    },
    "SK10": {
        "shaft": 10,
        "h": 20,
        "E": 21,
        "W": 42,
        "L": 14,
        "F": 32.8,
        "G": 6,
        "P": 18,
        "B": 32,
        "S": 5.5,
        "LB": 4,
    },
    "SK12": {
        "shaft": 12,
        "h": 23,
        "E": 21,
        "W": 42,
        "L": 14,
        "F": 37.5,
        "G": 6,
        "P": 20,
        "B": 32,
        "S": 5.5,
        "LB": 4,
    },
    "SK13": {
        "shaft": 13,
        "h": 23,
        "E": 21,
        "W": 42,
        "L": 14,
        "F": 37.5,
        "G": 6,
        "P": 20,
        "B": 32,
        "S": 5.5,
        "LB": 4,
    },
    "SK16": {
        "shaft": 16,
        "h": 27,
        "E": 24,
        "W": 48,
        "L": 16,
        "F": 44,
        "G": 8,
        "P": 25,
        "B": 38,
        "S": 5.5,
        "LB": 4,
    },
    "SK20": {
        "shaft": 20,
        "h": 31,
        "E": 30,
        "W": 60,
        "L": 20,
        "F": 51,
        "G": 10,
        "P": 30,
        "B": 45,
        "S": 6.6,
        "LB": 5,
    },
    "SK25": {
        "shaft": 25,
        "h": 35,
        "E": 35,
        "W": 70,
        "L": 24,
        "F": 60,
        "G": 12,
        "P": 38,
        "B": 56,
        "S": 6.6,
        "LB": 5,
    },
    "SK30": {
        "shaft": 30,
        "h": 42,
        "E": 42,
        "W": 84,
        "L": 28,
        "F": 70,
        "G": 12,
        "P": 44,
        "B": 64,
        "S": 9,
        "LB": 6,
    },
    "SK35": {
        "shaft": 35,
        "h": 50,
        "E": 49,
        "W": 98,
        "L": 32,
        "F": 82,
        "G": 15,
        "P": 50,
        "B": 74,
        "S": 11,
        "LB": 8,
    },
    "SK40": {
        "shaft": 40,
        "h": 60,
        "E": 57,
        "W": 114,
        "L": 36,
        "F": 95,
        "G": 16,
        "P": 60,
        "B": 90,
        "S": 11,
        "LB": 8,
    },
    "SK50": {
        "shaft": 50,
        "h": 70,
        "E": 63,
        "W": 126,
        "L": 40,
        "F": 120,
        "G": 18,
        "P": 74,
        "B": 100,
        "S": 14,
        "LB": 12,
    },
    "SK60": {
        "shaft": 60,
        "h": 80,
        "E": 74,
        "W": 148,
        "L": 45,
        "F": 136,
        "G": 18,
        "P": 90,
        "B": 120,
        "S": 14,
        "LB": 12,
    },
}


class SK:
    def __init__(self, modelNo="SK8"):
        self.params = model_params[modelNo]

    def get_part(self):
        self.sk = Part()
        W = self.params["W"]
        G = self.params["G"]
        P = self.params["P"]
        F = self.params["F"]
        L = self.params["L"]
        h = self.params["h"]
        B = self.params["B"]
        pf = PlaneFactory()

        def get_sketch_1():
            # Operation 1 - Extrusion
            s = Sketch(self.sk.xy())
            points = [
                Point(s, W / 2, 0),
                Point(s, W / 2, G),
                Point(s, P / 2, G),
                Point(s, P / 2, F),
                Point(s, -P / 2, F),
                Point(s, -P / 2, G),
                Point(s, -W / 2, G),
                Point(s, -W / 2, 0),
            ]
            lines = []
            for i in range(len(points)):
                lines.append(Line(points[i], points[(i + 1) % len(points)]))
            polygon = Polygon(lines)

            return polygon

        def get_shaft_hole():
            s = Sketch(self.sk.xy())
            center = Point(s, 0, h)
            e2 = Hole(center, self.params["shaft"] / 2, L)
            return e2

        def get_side_holes():
            s = Sketch(self.sk.xz())
            c1 = Point(s, B / 2, L / 2)
            c2 = Point(s, -B / 2, L / 2)
            holes = [
                Hole(c1, self.params["S"] / 2, -G),
                Hole(c2, self.params["S"] / 2, -G),
            ]
            return holes

        def get_cut():
            s = Sketch(self.sk.xy())
            r = Rectangle.from_2_points(Point(s, -0.5, F), Point(s, 0.5, h))
            return r

        def get_screw_hole():
            s = Sketch(self.sk.yz())
            # no data on the height of hole.
            center = Point(s, -L / 2, F - self.params["LB"])
            e2 = Hole(center, self.params["LB"] / 2, P / 2)
            return e2

        e = Extrusion(get_sketch_1(), L)
        self.sk.add_operation(e)
        self.sk.add_operation(get_shaft_hole())
        self.sk.add_operation(Extrusion(get_cut(), L, cut=True))

        for hole in get_side_holes():
            self.sk.add_operation(hole)
        self.sk.add_operation(get_screw_hole())

        return self.sk


# leave this line it's used for loading locally examples
# show(SK().get_part())
