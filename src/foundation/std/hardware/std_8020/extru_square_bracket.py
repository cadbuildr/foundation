from foundation import *


dimensions = {
    "40-4302": {"A": 40, "B": 40, "C": 6, "D": 20, "E": 18, "F": 36, "G": 8.3}
}

# TODO add more to the list from the 8020 website


class StandardCornerBracket:
    """Example : https://8020.net/40-4302.html"""

    def __init__(self, model="40-4302"):
        """
        :param A: length x
        :param B: length y
        :param C: thickness
        :param D: hole X
        :param E: hole Y
        :param F: width
        :param g: hole diameter
        """

        self.model = model
        self.A = dimensions[model]["A"]
        self.B = dimensions[model]["B"]
        self.C = dimensions[model]["C"]
        self.D = dimensions[model]["D"]
        self.E = dimensions[model]["E"]
        self.F = dimensions[model]["F"]
        self.G = dimensions[model]["G"]

    def get_L_extru_operation(self):
        # operation 1 Make a L bracket and extrude it

        s = Sketch(self.component.origin_planes[0])
        p1 = Point(s, self.A, 0)
        p2 = Point(s, self.A, self.C)
        p3 = Point(s, self.C, self.C)
        p4 = Point(s, self.C, self.B)
        p5 = Point(s, 0, self.B)
        p6 = Point(s, 0, 0)

        points = [p1, p2, p3, p4, p5, p6]
        lines = [
            Line(points[i], points[(i + 1) % len(points)]) for i in range(len(points))
        ]
        polygon = Polygon(s, lines)

        e = Extrusion(polygon, self.F)
        self.component.add_operation(e)

    def get_holes(self):
        # operation 2 Make holes on the 2 sides
        s = Sketch(self.component.origin_planes[1])
        p1 = Point(s, -self.D, self.E)
        h = Hole(p1, self.G / 2, -self.C)
        self.component.add_operation(h)

        s = Sketch(self.component.origin_planes[2])
        p2 = Point(s, -self.E, self.D)
        h = Hole(p2, self.G / 2, self.C)
        self.component.add_operation(h)

    def get_part(self):
        self.component = start_component()
        self.get_L_extru_operation()
        self.get_holes()
        return self.component


class SquareBracket40_4302(StandardCornerBracket):
    """Example : https://8020.net/40-4302.html"""

    def __init__(self):
        super().__init__(model="40-4302")


# show(StandardCornerBracket().get_part())
