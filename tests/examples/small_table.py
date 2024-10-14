from foundation import *

# Operations


def get_small_table():
    small_table = Part()
    plane1 = small_table.xy()
    s = Sketch(plane1)
    p = Point(s, 0, 0)
    square_construct = Square.from_center_and_side(p, 30)
    circles = [Circle(p, radius=3) for p in square_construct.get_points()]
    extrusions = [Extrusion(c, 15) for c in circles]

    pf = PlaneFactory()
    s2 = Sketch(pf.get_parallel_plane(plane1, 15))
    p2 = Point(s2, 0, 0)
    square = Square.from_center_and_side(p2, 40)
    extrusions.append(Extrusion(square, 3))

    small_table.add_operations(extrusions)
    return small_table


# show(get_small_table())
