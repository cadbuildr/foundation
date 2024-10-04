from foundation.types.part import Part
from foundation.types.assembly import Assembly
from foundation.operations.extrude import Extrusion, Hole
from foundation.operations.lathe import Lathe
from foundation.operations.fillet import Fillet
from foundation.operations.chamfer import Chamfer
from foundation.operations.loft import Loft
from foundation.operations.shell import Shell
from foundation.sketch.sketch import Sketch, SketchOrigin
from foundation.sketch.primitives.line import Line
from foundation.sketch.axis import Axis
from foundation.sketch.point import Point
from foundation.sketch.closed_sketch_shape import (
    Circle,
    Ellipse,
    SVGShape,
    Polygon,
    Hexagon,
    RoundedCornerPolygon,
)
from foundation.sketch.rectangle import Rectangle, Square, RoundedCornerRectangle
from foundation.geometry.plane import Plane, PlaneFactory
from foundation.geometry.frame import Frame
from foundation.types.parameters import (
    FloatParameter,
    IntParameter,
    StringParameter,
    BoolParameter,
)
from foundation.rendering.material import Material
from foundation.types.serializable import serializable_nodes
from foundation.geometry.tf_helper import TFHelper
from foundation.operations.grid import GridXY
from foundation.sketch.pattern import *
from foundation.types.parameterUI import ParameterUI
from foundation.sketch.sketch import Sketch
from foundation.types.node import Node
from foundation.utils_ext import showExt
from foundation.utils import show
from foundation.types.point_3d import Point3D


def reset_ids():
    Node.reset_ids()
    Part.reset_ids()
    Assembly.reset_ids()
