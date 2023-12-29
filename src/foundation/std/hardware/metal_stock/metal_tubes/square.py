from foundation import *


# A class for making a square tube with a given width and height and a given thickness
class SquareTube:
    def __init__(self, height=100, width=20, thickness=2):
        self.height = height
        self.width = width
        self.thickness = thickness

    def get_part(self):
        component = start_component()
        xz_p, xy_p, yz_p = component.origin_planes
        s = Sketch(xz_p)
        center = s.origin
        square_shape_outer = Square.from_center_and_side(center, self.width)
        square_shape_inner = Square.from_center_and_side(
            center, self.width - self.thickness
        )

        # TODO combine shapes to perform extrusion at once.
        extrusion = Extrusion(square_shape_outer, self.height)
        extrusion2 = Extrusion(square_shape_inner, self.height, cut=True)
        component.add_operation(extrusion)
        component.add_operation(extrusion2)
        end_plane = component.pf.get_parallel_plane(xz_p, self.height)

        component.add_construction_element("end_plane", end_plane)
        component.add_construction_element("start_plane", xz_p)

        side_planes = [
            component.pf.get_parallel_plane(xy_p, self.width / 2),
            component.pf.get_parallel_plane(yz_p, self.width / 2),
            component.pf.get_parallel_plane(xy_p, -self.width / 2),
            component.pf.get_parallel_plane(yz_p, -self.width / 2),
        ]
        component.add_construction_element("side_planes", side_planes)
        return component
