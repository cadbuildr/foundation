import math
from foundation import *
from foundation.std.hardware.std_8020.extru_assembly_helper import ExtruAssemblyHelper


class TableStructure:
    def __init__(
        self,
        width=900,
        depth=500,
        height=800,
        feet_spacing_width=400,
        depth_feet_offset=100,
    ):
        self.width = width
        self.depth = depth
        self.height = height
        self.feet_spacing_width = feet_spacing_width
        self.depth_feet_offset = depth_feet_offset
        self.assembly = start_assembly()

    def get_structure_section(self):
        helper = ExtruAssemblyHelper()
        helper.add_u_shape(self.height, self.depth - (2 * self.depth_feet_offset))
        helper.back_one()
        helper.compose_L_turn(
            self.feet_spacing_width, direction="forward", type="before"
        )
        helper.back_one()
        helper.back_one()
        helper.compose_L_turn(
            self.feet_spacing_width, direction="forward", type="afterside"
        )

        return helper.get_assy()

    def get_assy(self):
        # calculate how many U extrusions we need
        n_u = math.ceil(self.width / self.feet_spacing_width)
        self.assembly = start_assembly()
        for i in range(n_u - 1):
            tf_helper = TFHelper()
            subassy = self.get_structure_section()
            tf_helper.translate_x((self.feet_spacing_width + 40) * i)
            self.assembly.add_component(subassy, tf_helper.get_tf())

        tf_helper = TFHelper()
        helper = ExtruAssemblyHelper()
        helper.add_u_shape(self.height, self.depth - (2 * self.depth_feet_offset))
        tf_helper.translate_x(-(self.feet_spacing_width + 40) * (n_u - 2))

        self.assembly.add_component(helper.get_assy(), tf_helper.get_tf())

        return self.assembly


# show(TableStructure().get_assy())
