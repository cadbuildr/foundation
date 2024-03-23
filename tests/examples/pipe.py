from foundation import *
import numpy as np


def get_pipe():
    pipe = start_component()
    s = Sketch(pipe.xy())
    p1 = Point(s, 0, 0)
    # outer extrusion
    circle = Circle(p1, 1.5)
    e = Extrusion(circle, 4)
    # inside extrusion using cut
    circle2 = Circle(p1, 1)
    e2 = Extrusion(circle2, 4, cut=True)
    pipe.add_operation(e)
    pipe.add_operation(e2)
    return pipe


def get_pipe_with_holes():
    pipe = get_pipe()
    # add holes
    pf = PlaneFactory()

    plane1 = pipe.xy()
    plane2 = pf.get_parallel_plane(plane1, 2)
    plane3 = pf.get_angle_plane_from_axis(plane2, plane2.get_x_axis(), np.pi / 2)
    s = Sketch(plane3)
    p1 = Point(s, 0, 0)
    h = Hole(p1, 0.3, 3)
    pipe.add_operation(h)
    return pipe


# leave this line it's used for loading locally examples
# show(get_pipe_with_holes())
