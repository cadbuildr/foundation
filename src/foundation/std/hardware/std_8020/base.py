from foundation import *
import math


dimension_table = {
    "1010": dict(
        width_inside_tslot=0.356 * 25.4,
        width_tslot_diagonals=0.087 * 25.4,
        tslot_side_to_side=0.584 * 25.4,
        width_cut=0.256 * 25.4,
        hole_diameter=0.205 * 25.4,
    ),
    "1515": dict(
        width_inside_tslot=0.531 * 25.4,
        width_tslot_diagonals=0.160 * 25.4,
        tslot_side_to_side=0.810 * 25.4,
        width_cut=0.320 * 25.4,
        hole_diameter=0.262 * 25.4,
    ),
    "20-2020": dict(
        width_inside_tslot=7.32,
        width_tslot_diagonals=1.5,
        tslot_side_to_side=11.99,
        width_cut=5.26,
        hole_diameter=4.19,
    ),
    "25-2525": dict(
        width_inside_tslot=8.76,
        width_tslot_diagonals=2.13,
        tslot_side_to_side=14.69,
        width_cut=6.5,
        hole_diameter=5,
    ),
    "30-3030": dict(
        width_inside_tslot=11.64,
        width_tslot_diagonals=2.54,
        tslot_side_to_side=16.51,
        width_cut=8.14,
        hole_diameter=6.65,
    ),
    "40-4040": dict(
        width_inside_tslot=15.36,
        width_tslot_diagonals=3.3,
        tslot_side_to_side=20.57,
        width_cut=8.13,
        hole_diameter=6.81,
    ),
    "45-4545": dict(
        width_inside_tslot=19,
        width_tslot_diagonals=3.25,
        tslot_side_to_side=20.09,
        width_cut=10.13,
        hole_diameter=10,
    ),
}


class BaseSquare:
    """Base component of a 8020 metal tube."""

    def __init__(self, height, width, table):
        self.height = height
        self.width = width
        self.table = table

    def get_part(self):
        # TODO add chamfers

        component = start_component()
        s = Sketch(component.origin_planes[0])
        center = s.origin

        # Main square
        square_shape_outer = Square.from_center_and_side(center, self.width)
        extrusion = Extrusion(square_shape_outer, self.height)
        component.add_operation(extrusion)

        # middle circle inside the square
        # TODO table for all sizes for hole.
        square_shape_inner = Circle(center, self.table["hole_diameter"] / 2)
        extrusion2 = Extrusion(square_shape_inner, self.height, cut=True)
        component.add_operation(extrusion2)

        # TSLOT
        width_inside_tslot = self.table["width_inside_tslot"]
        width_tslot_diagonals = self.table["width_tslot_diagonals"]
        width_tslot_diagonals_hor = width_tslot_diagonals / math.sqrt(2)
        tslot_side_to_side = self.table["tslot_side_to_side"]
        height_tslot = width_inside_tslot / 2 - width_tslot_diagonals_hor
        width_cut = self.table["width_cut"]

        p1 = Point(s, width_inside_tslot / 2, -height_tslot)
        p2 = Point(s, width_inside_tslot / 2, height_tslot)

        x_p3 = tslot_side_to_side / 2 + width_tslot_diagonals_hor
        y_p3 = tslot_side_to_side / 2
        p3 = Point(s, x_p3, y_p3)

        y_p5 = width_cut / 2

        p4 = Point(s, x_p3, y_p5)
        p5 = Point(s, self.width / 2, y_p5)
        p6 = Point(s, self.width / 2, -y_p5)
        p7 = Point(s, x_p3, -y_p5)

        p8 = Point(s, x_p3, -y_p3)

        lines = [
            Line(p1, p8),
            Line(p8, p7),
            Line(p7, p6),
            Line(p6, p5),
            Line(p5, p4),
            Line(p4, p3),
            Line(p3, p2),
            Line(p2, p1),
        ]
        poly = Polygon(s, lines)
        extrusion3 = Extrusion(poly, self.height, cut=True)
        component.add_operation(extrusion3)

        # rotate and repeat extrusion 3 for all 4 sides of the tube
        shapes = CircularPattern(center, 4).run(poly)

        extrusions = [Extrusion(shape, self.height, cut=True) for shape in shapes]
        for extrusion in extrusions:
            component.add_operation(extrusion)

        return component


class Extru1010(BaseSquare):
    "1 inch by 1 inch square tube."

    def __init__(self, height):
        super().__init__(height, 25.4, table=dimension_table["1010"])


class Extru1515(BaseSquare):
    "1.5 inch by 1.5 inch square tube."

    def __init__(self, height):
        super().__init__(height, 25.4 * 1.5, table=dimension_table["1515"])


class Extru20_2020(BaseSquare):
    "20mmx 20mm square tube."

    def __init__(self, height):
        super().__init__(height, 20, table=dimension_table["20-2020"])


class Extru25_2525(BaseSquare):
    "25mmx 25mm square tube."

    def __init__(self, height):
        super().__init__(height, 25, table=dimension_table["25-2525"])


class Extru30_3030(BaseSquare):
    "30mmx 30mm square tube."

    def __init__(self, height):
        super().__init__(height, 30, table=dimension_table["30-3030"])


class Extru40_4040(BaseSquare):
    "40mmx 40mm square tube."

    def __init__(self, height):
        super().__init__(height, 40, table=dimension_table["40-4040"])


class Extru45_4545(BaseSquare):
    "45mmx 45mm square tube."

    def __init__(self, height):
        super().__init__(height, 45, table=dimension_table["45-4545"])
