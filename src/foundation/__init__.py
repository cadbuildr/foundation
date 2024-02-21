from foundation.types.component import Component
from foundation.types.assembly import Assembly
from foundation.operations.extrude import Extrusion, Hole
from foundation.operations.lathe import Lathe
from foundation.sketch.sketch import Sketch, SketchOrigin
from foundation.sketch.line import Line
from foundation.sketch.axis import Axis
from foundation.sketch.point import Point
from foundation.sketch.closed_sketch_shape import Circle, Ellipse, Polygon, Hexagon
from foundation.sketch.rectangle import Rectangle, Square
from foundation.geometry.plane import PlaneFromFrame
from foundation.geometry.frame import OriginFrame, Frame
from foundation.types.parameters import (
    FloatParameter,
    IntParameter,
    StringParameter,
    BoolParameter,
)
from foundation.rendering.material import Material
from foundation.types.serializable import serializable_nodes
from foundation.utils import start_component, start_assembly
from foundation.geometry.tf_helper import TFHelper
from foundation.operations.grid import GridXY
from foundation.sketch.pattern import *
from foundation.types.parameterUI import ParameterUI
from foundation.sketch.sketch import Sketch
from foundation.types.node import Node


def reset_ids():
    Node.reset_ids()
    Component.reset_ids()
    Assembly.reset_ids()
