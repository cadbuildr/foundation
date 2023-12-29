from foundation import *


def get_brady_laptop_holder():
    brady_lh = start_component()
    # Operation 1 Ellipse extrusion
    xy, xz, yz = brady_lh.origin_planes
    # TODO simplify access to y plane.
    pf = PlaneFactory()
    s = Sketch(xz)
    p1 = Point(s, 0, 0)
    width, length, height = 50, 40, 40
    ellipse = Ellipse(p1, width / 2, height)
    e = Extrusion(ellipse, length)
    brady_lh.add_operation(e)

    # Operation 2 cut bottom half
    s2 = Sketch(xz)
    p1 = Point(s2, -width, 0)
    p4 = Point(s2, width, 0)
    p3 = Point(s2, width, -width)
    p2 = Point(s2, -width, -width)
    l1 = Line(p1, p2)
    l2 = Line(p2, p3)
    l3 = Line(p3, p4)
    l4 = Line(p4, p1)
    square = Polygon(s, [l1, l2, l3, l4])
    e = Extrusion(square, length, cut=True)
    brady_lh.add_operation(e)

    # Operation3
    # slot
    s3 = Sketch(xz)
    cut_height = 0.75 * height
    cut_width = 0.3 * width
    p1 = Point(s3, cut_width / 2, height)
    p2 = Point(s3, -cut_width / 2, height)
    p3 = Point(s3, -cut_width / 2, height - cut_height)
    p4 = Point(s3, cut_width / 2, height - cut_height)
    l1 = Line(p1, p2)
    l2 = Line(p2, p3)
    l3 = Line(p3, p4)
    l4 = Line(p4, p1)
    square = Polygon(s, [l1, l2, l3, l4])
    e = Extrusion(square, 50, cut=True)
    brady_lh.add_operation(e)

    # Operation 4
    # 2 ellipses cut on the side
    ellipse_b = 0.4 * height
    ellipse_a = length / 6
    s4 = Sketch(yz)
    c1 = Point(s4, 0, -length / 4)
    c2 = Point(s4, 0, -3 * length / 4)
    ellipse1 = Ellipse(c1, ellipse_b, ellipse_a)
    ellipse2 = Ellipse(c2, ellipse_b, ellipse_a)
    e1 = Extrusion(ellipse1, start=-width / 2, end=width / 2, cut=True)
    e2 = Extrusion(ellipse2, start=-width / 2, end=width / 2, cut=True)
    brady_lh.add_operation(e1)
    brady_lh.add_operation(e2)
    return brady_lh


# TODO add CustomClosedSketchShape in the serializable nodes
# def get_brady_laptop_holder_simpler():
#     # params :
#     width, length, height = 50, 40, 40

#     brady_lh = start_component()
#     xz_p, xy_p, yz_p = brady_lh.origin_planes

#     s = Sketch(xz_p)
#     # Operation 1 : Half Ellipse extrusion
#     ellipse_arc = EllipseArc(s.origin, width / 2, height, 0, np.pi)
#     e = Extrusion(CustomClosedSketchShape([ellipse_arc]), length)
#     brady_lh.add_operation(e)

#     # Operation2 : slot2
#     s3 = Sketch(xz_p)
#     cut_height = 0.75 * height
#     cut_width = 0.3 * width
#     cut_top_left = Point(s3, -cut_width / 2, height)
#     cut_bottom_right = Point(s3, cut_width / 2, height - cut_height)
#     square = Rectangle.from_2_points(cut_top_left, cut_bottom_right)
#     e = Extrusion(square, 50, cut=True)
#     brady_lh.add_operation(e)

#     # Operation 4
#     # 2 ellipses cut on the side
#     ellipse_b = 0.4 * height
#     ellipse_a = length / 6
#     cut_plane = brady_lh.pf.get_parallel_plane(yz_p, -width / 2)
#     s4 = Sketch(cut_plane)
#     c1 = Point(s4, -length / 4, 0)
#     c2 = Point(s4, -3 * length / 4, 0)
#     ellipse1 = Ellipse(c1, ellipse_a, ellipse_b)
#     ellipse2 = Ellipse(c2, ellipse_a, ellipse_b)
#     e1 = Extrusion(ellipse1, width, cut=True)
#     e2 = Extrusion(ellipse2, width, cut=True)
#     brady_lh.add_operation(e1)
#     brady_lh.add_operation(e2)

#     return brady_lh


# show(get_brady_laptop_holder())
