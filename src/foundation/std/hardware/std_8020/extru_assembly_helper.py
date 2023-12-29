import math
from foundation import *
from foundation.std.hardware.std_8020.base import Extru40_4040
from foundation.std.hardware.std_8020.extru_square_bracket import SquareBracket40_4302
import numpy as np

# by series, pre-import Components used for the assembly
sub_components = {"extrusion": Extru40_4040, "bracket": SquareBracket40_4302}


class ExtruAssemblyHelper:
    def __init__(self, series="40"):
        self.series = series
        self.assembly = start_assembly()
        self.extrusions = []
        self.tfs = []
        self.current_index = None
        self.tf_helper = TFHelper()

    def add_extrusion(self, height, tf=np.eye(4, dtype="float")):
        extru = sub_components["extrusion"](height)
        self.assembly.add_component(extru.get_part(), tf)
        self.extrusions.append(extru)
        self.tfs.append(tf)
        if self.current_index is None:
            self.current_index = 0
        else:
            self.current_index += 1
        return extru

    def add_bracket(self, tf=np.eye(4, dtype="float")):
        bracket = sub_components["bracket"]()
        self.assembly.add_component(bracket.get_part(), tf)

    def compose_L_turn(
        self, length, direction="right", type="after", with_bracket=True
    ):
        """
        Add a bracket, and an extrusion to the assembly.
        length: the length of the new extrusion
        direction: 'right' or 'left' or 'forward' or 'backward' (direction of the new extrusion)
        type: 'after' or 'before' position of the new extrusion either at the end or on the side before the end
        """

        if self.current_index == 0:
            self.tf_helper.set_init()
        else:
            self.tf_helper.set_tf(self.tfs[self.current_index])
        previous_extru = self.extrusions[self.current_index]

        # add the extrusion
        translation_dim = previous_extru.height
        if type == "after":
            translation_dim += previous_extru.width / 2
        elif type == "before":
            translation_dim -= previous_extru.width / 2
        elif type == "afterside":  # after but also far on the side
            translation_dim += previous_extru.width / 2

        self.tf_helper.translate([0, 0, translation_dim], rotate=True)

        if direction == "right":
            self.tf_helper.rotate([1, 0, 0], math.pi / 2)
        elif direction == "left":
            self.tf_helper.rotate([1, 0, 0], -math.pi / 2)
        elif direction == "backward":
            self.tf_helper.rotate([0, 1, 0], math.pi / 2)
        elif direction == "forward":
            self.tf_helper.rotate([0, 1, 0], -math.pi / 2)

        if type == "after":
            self.tf_helper.translate([0, 0, -previous_extru.width / 2], rotate=True)
        elif type == "before":
            self.tf_helper.translate([0, 0, previous_extru.width / 2], rotate=True)
        elif type == "afterside":  # after but also far on the side
            self.tf_helper.translate([0, 0, previous_extru.width / 2], rotate=True)

        self.add_extrusion(length, self.tf_helper.get_tf())

        # add the bracket
        # TODO fix extrusions bug ( symetric)
        # TODO holes get moved not correctly
        bracket_tf = self.tf_helper.get_tf()
        bracket_tfh = TFHelper()
        bracket_tfh.set_tf(bracket_tf)

        F = sub_components["bracket"]().F  # width of bracket is a bit less

        if direction == "right":
            bracket_tfh.translate(
                [
                    F / 2,
                    -previous_extru.width / 2,
                    previous_extru.width * (type in ["after"]),
                ],
                rotate=True,
            )
            bracket_tfh.rotate([1, 0, 0], math.pi / 2)
            bracket_tfh.rotate([0, 1, 0], -math.pi / 2)
        elif direction == "left":
            bracket_tfh.translate(
                [
                    -F / 2,
                    previous_extru.width / 2,
                    previous_extru.width * (type in ["after"]),
                ],
                rotate=True,
            )
            bracket_tfh.rotate([1, 0, 0], math.pi / 2)
            bracket_tfh.rotate([0, 1, 0], math.pi / 2)
        elif direction == "forward":
            bracket_tfh.translate(
                [
                    -previous_extru.width / 2,
                    -F / 2,
                    previous_extru.width * (type in ["after"]),
                ],
                rotate=True,
            )
            bracket_tfh.rotate([1, 0, 0], math.pi / 2)
            bracket_tfh.rotate([0, 1, 0], math.pi)
        elif direction == "backward":
            bracket_tfh.translate(
                [
                    previous_extru.width / 2,
                    F / 2,
                    previous_extru.width * (type in ["after"]),
                ],
                rotate=True,
            )
            bracket_tfh.rotate([1, 0, 0], math.pi / 2)
            bracket_tfh.rotate([0, 1, 0], 0)

        # bracket_tfh.translate([0, 0, -previous_extru.width / 2], rotate=True)

        self.add_bracket(bracket_tfh.get_tf())

    def add_u_shape(self, height, width, type="after"):
        self.add_extrusion(height)
        self.compose_L_turn(width, direction="right", type=type)
        if type == "after":
            o_type = "before"
        elif type == "before":
            o_type = "after"
        self.compose_L_turn(height, direction="right", type=o_type)

    def compose_u_shape(self, height, width, type="after", fdir="right", ftype="after"):
        self.compose_L_turn(height, direction=fdir, type=ftype)
        self.compose_L_turn(width, direction="right", type=type)
        if type == "after":
            o_type = "before"
        elif type == "before":
            o_type = "after"
        self.compose_L_turn(height, direction="right", type=o_type)

    def get_assy(self):
        return self.assembly

    def back_one(self):
        if self.current_index > 0:
            self.current_index -= 1

    def forward_one(self):
        if self.current_index < len(self.extrusions):
            self.current_index += 1


# U = ExtruAssemblyHelper()
# U.add_u_shape(300, 200, type="after")
# show(U.get_assy())
