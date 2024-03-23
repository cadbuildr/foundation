from foundation import *


def get_cube():
    cube = start_component()
    # Operation 1
    s = Sketch(cube.xy())
    p1 = Point(s, 0, 0)
    p2 = Point(s, 1, 0)
    p3 = Point(s, 1, 1)
    p4 = Point(s, 0, 1)

    l1 = Line(p1, p2)
    l2 = Line(p2, p3)
    l3 = Line(p3, p4)
    l4 = Line(p4, p1)
    square = Polygon(s, [l1, l2, l3, l4])

    e = Extrusion(square, 1)
    cube.add_operation(e)
    return cube


# leave this line it's used for loading locally examples
# show(get_cube())
