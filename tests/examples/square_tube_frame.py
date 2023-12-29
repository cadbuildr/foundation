from foundation import *
from foundation.std.hardware.metal_stock.metal_tubes.square import SquareTube
import numpy as np
import math

# Operations


def get_square_frame():
    tube_len = 200
    tube_width = 50
    tf_h = TFHelper()

    assy = start_assembly()
    tubes = [SquareTube(tube_len, tube_width, 2).get_part() for i in range(4)]

    for i, tube in enumerate(tubes):
        # a bit cryptic but it works, TODO change with constraits instead of manually calculating TFs
        tf = (
            tf_h.translate([(tube_width / 2), 0, 0], rotate=True)
            .rotate([0, 1, 0], math.pi / 2)
            .translate([-(tube_len + tube_width / 2), 0, 0], rotate=True)
            .get_tf()
        )
        assy.add_component(tube, tf)

    return assy


# TODO when GCS is ready
# def get_square_frame_simplified():
#     tube_len = 200
#     tube_width = 50
#     tubes = [SquareTube(tube_len, tube_width, 2).get_component() for i in range(4)]
#     jf = JointFactory()
#     assy = start_assembly()
#     # add elements
#     for t in tubes:
#         assy.add_component(t)

#     # constraints
#     jf.anchor_element(tubes[0])
#     for i, t in enumerate(tubes[:3]):
#         j = i + 1  # cycle next tube
#         other_tube = tubes[j]
#         sp = t.get_construction_element("start_plane")
#         sides = t.get_construction_element("side_planes")[0]
#         other_sides = other_tube.get_construction_element("side_planes")[0]
#         jf.plane_coincidence(sp, other_sides[0])
#         jf.plane_coincidence(sides[1], other_sides[1])

#     return assy


# leave this line it's used for loading locally examples
# show(get_square_frame())
