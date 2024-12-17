from cadbuildr.foundation import *


def get_cylinder():
    # Operations

    # Example
    # Create Geometric construction basics (Origin, Origin Plane ...)
    # Operation 1 Create Sketch
    # Operation 2 Create Extrusion

    cylinder = Part()
    # Operation 1
    s = Sketch(cylinder.xy())
    p1 = Point(s, 0, 0)
    circle = Circle(p1, 1)
    # Operation 2
    e = Extrusion(circle, 1)
    cylinder.add_operation(e)
    return cylinder


# leave this line it's used for loading locally examples
# show(get_cylinder())
