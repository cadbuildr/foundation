from .brady_laptop_holder import (
    get_brady_laptop_holder,
    # get_brady_laptop_holder_simpler,
)
from .small_table import get_small_table
from .double_cylinder import get_double_cylinder
from .cube import get_cube
from .cylinder import get_cylinder
from .pipe import get_pipe, get_pipe_with_holes
from .butterfly_cone import get_butterfly_cone


examples = {
    "butterfly_cone": get_butterfly_cone,
    "pipe_with_holes": get_pipe_with_holes,
    "small_table": get_small_table,
    "double_cylinder": get_double_cylinder,
    "cube": get_cube,
    "cylinder": get_cylinder,
    "pipe": get_pipe,
}


def get_all_examples():
    res = {}
    for name, example in examples.items():
        res[name] = example()
    return res
