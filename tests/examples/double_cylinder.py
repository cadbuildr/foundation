from foundation import *


def get_double_cylinder():
    double_extrusion = start_component()
    plane1 = double_extrusion.xy()
    s = Sketch(plane1)
    p1 = Point(s, 0, 0)
    circle = Circle(p1, 1)
    # Operation 1 Extrude circle
    e = Extrusion(circle, 3)
    double_extrusion.add_operation(e)
    # Operation 2 Second extrusion
    pf = PlaneFactory()
    s2 = Sketch(pf.get_parallel_plane(plane1, 3))
    p2 = Point(s2, 0, 0)
    circle = Circle(p2, 3)
    e2 = Extrusion(circle, 1)
    double_extrusion.add_operation(e2)
    return double_extrusion


# leave this line it's used for loading locally examples
# show(get_double_cylinder())
