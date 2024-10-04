from foundation import *


def get_butterfly_cone():
    butterfly_cone = Part()
    # Operation 1
    s = Sketch(butterfly_cone.xy())
    p1 = Point(s, 1, 0)
    p2 = Point(s, 5, 0)
    p4 = Point(s, 5, 10)
    p5 = Point(s, 1, 10)

    p6 = Point(s, -4, 0)
    p7 = Point(s, -6, 2)

    axis = Axis(Line(p6, p7))
    lines = [Line(p1, p2), Line(p2, p4), Line(p4, p5), Line(p5, p1)]
    polygon = Polygon(lines)
    # Operation 2
    e = Lathe(polygon, axis)
    butterfly_cone.add_operation(e)
    return butterfly_cone


# leave this line it's used for loading locally examples
# show(get_butterfly_cone())
