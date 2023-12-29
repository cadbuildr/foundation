from foundation import *
from foundation.std.hardware.std_8020.table_structure import TableStructure
from foundation.std.hardware.std_8020.extrufeet import FeetAssy


# Class to build a table with 4 8020 extrusion legs and a square top with 15 mm plywood
class TableSquare:
    def __init__(
        self,
        table_height=800,
        table_width=1000,
        depth=500,
        top_thickness=20,
        feet_spacing=400,
        depth_feet_offset=50,
    ):
        self.table_height = table_height
        self.table_width = table_width
        self.top_thickness = top_thickness
        self.depth = depth
        self.feet_spacing = feet_spacing
        self.depth_feet_offset = depth_feet_offset

    def get_structure(self):
        # add structure
        structure = TableStructure(
            width=self.table_width,
            depth=self.depth,
            height=self.table_height - 40,
            feet_spacing_width=self.feet_spacing,
            depth_feet_offset=self.depth_feet_offset,
        )
        return structure.get_assy()

    def get_top(self):
        # add top
        top = start_component()
        s = Sketch(top.origin_planes[0])

        # make rectangle extrusion
        points = [
            Point(s, 0, 0),
            Point(s, self.table_width, 0),
            Point(s, self.table_width, self.depth),
            Point(s, 0, self.depth),
        ]
        lines = [Line(p1, p2) for p1, p2 in zip(points, points[1:] + [points[0]])]
        rectangle = Polygon(s, lines)
        e = Extrusion(rectangle, self.top_thickness)
        top.add_operation(e)

        m = Material()
        m.set_diffuse_color("plywood")
        top.set_material(m)

        return top

    def get_feet(self):
        grid = GridXY(
            FeetAssy(),
            3,
            2,
            self.feet_spacing + 40,
            self.depth - 2 * self.depth_feet_offset - 40,
        )
        return grid.get_assy()

    def get_assembly(self):
        assembly = start_assembly()

        # add structure
        structure = self.get_structure()
        tf_helper = TFHelper()
        tf_helper.translate_x(
            self.feet_spacing + (self.table_width % self.feet_spacing) / 2
        )  # + 20 + (self.table_width % self.feet_spacing))
        tf_helper.translate_y(self.depth - self.depth_feet_offset - 20)

        assembly.add_component(structure, tf_helper.get_tf())

        # add top
        top = self.get_top()
        tf_helper = TFHelper()
        tf_helper.translate_z(self.table_height)
        assembly.add_component(top, tf_helper.get_tf())

        # add feet
        feet = self.get_feet()
        tf_helper = TFHelper()
        tf_helper.translate_z(0)
        tf_helper.translate_x((self.table_width % self.feet_spacing) / 2 - 40)
        tf_helper.translate_y(self.depth_feet_offset + 20)
        tf_helper.translate_z(-40)

        assembly.add_component(feet, tf_helper.get_tf())

        return assembly


# leave this line it's used for loading locally examples
# show(TableSquare().get_assembly())
