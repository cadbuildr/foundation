# %%

import unittest
from itertools import count

# Import necessary classes from your foundation package
from foundation import Assembly, reset_ids, show
from tests.examples.cube import get_cube


# class TestDAG(unittest.TestCase):


#     def test_duplicate_cubes_dag_efficiency(self):
# Create two identical cubes


class ManyCubeAssembly(Assembly):
    def __init__(self, num_cubes):
        super().__init__()
        self.num_cubes = num_cubes
        for i in range(num_cubes):
            cube = get_cube(15)
            cube.translate([i * 20, 0, 0])
            self.add_component(cube)


# Serialize to DAG
# dag = ManyCubeAssembly(5).to_dag()

# assembly_node_count = len(dag)
# print(assembly_node_count)
# reset_ids()
show(ManyCubeAssembly(150))
# 150 -> 1174ms (~1/1.5 sec)
# 500 -> 3850 ms
# %%
# %%
