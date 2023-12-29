from tests.examples.brady_laptop_holder import (
    get_brady_laptop_holder,
    # get_brady_laptop_holder_simpler,
)
from tests.examples.small_table import get_small_table
from tests.examples.double_cylinder import get_double_cylinder
from tests.examples.cube import get_cube
from tests.examples.cylinder import get_cylinder
from tests.examples.pipe import get_pipe, get_pipe_with_holes
from tests.examples.butterfly_cone import get_butterfly_cone
from tests.examples.square_tube_frame import get_square_frame

# from surface.std.hardware.metal_stock.metal_tubes.square import SquareTube

examples = {
    "butterfly_cone": get_butterfly_cone,
    "pipe_with_holes": get_pipe_with_holes,
    "small_table": get_small_table,
    "double_cylinder": get_double_cylinder,
    "cube": get_cube,
    "cylinder": get_cylinder,
    "pipe": get_pipe,
    # "brady_laptop_holder": get_brady_laptop_holder_simpler,
    "squaretube": get_square_frame,
}


def get_all_examples():
    res = {}
    for name, example in examples.items():
        res[name] = example()
    return res
