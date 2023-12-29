# %%
from foundation import utils
from foundation.sketch.point import Point
from foundation.sketch.line import Line
from foundation.sketch.sketch import Sketch
from foundation.operations.extrude import Extrusion
from foundation.sketch.closed_sketch_shape import Polygon
import pprint
import json
from tests.examples import examples, get_cube
from foundation.std import parts
from foundation.types.serializable import serializable_nodes
import traceback
import os


def test_serialize_cube():
    cube = get_cube()
    ser_cube = cube.to_dict(serializable_nodes=serializable_nodes)
    print(json.dumps(ser_cube))


def test_serialize_all_examples():
    for ex, func in examples.items():
        print(f"Serializing {ex}")
        part = func()
        ser_part = part.to_dict(serializable_nodes=serializable_nodes)
        # print(json.dumps(ser_example))


def test_serialize_all_std():
    for p, func in parts.items():
        print(f"Serializing {p}")
        part = func()
        ser_part = part.to_dict(serializable_nodes=serializable_nodes)


# TODO Should we keep this somehow ? Maybe for managing db and data consistency ?
# def test_tutorial_examples():
#     rel_path = "../../../frontend/src/tutorial_src/"
#     path = os.path.join(os.path.dirname(os.path.abspath(__file__)), rel_path)
#     # list all the files in the path
#     files = os.listdir(path)

#     pre_import_str = """
# import sys
# from surface.db.schema import Repo
# from itertools import count
# global mycompiler
# mycompiler = self
# import foundation
# foundation.show = lambda component: mycompiler.compile(component)
#     """

#     class Compiler:
#         def __init__(self):
#             pass

#         def compile(self, component):
#             self.component = component

#     for f in files:
#         if f.endswith(".py"):
#             print(f"Serializing {f}")

#             content = open(path + f).read()
#             print(content)
#             c = Compiler()
#             shared = {
#                 "self": c,
#             }
#             exec(pre_import_str, shared)
#             try:
#                 exec(content, shared)
#             except Exception as e:
#                 traceback.print_exc()
#                 print("Error in file: ", f)
#             print(c.component)
#             c.component.to_dict(serializable_nodes=serializable_nodes)
