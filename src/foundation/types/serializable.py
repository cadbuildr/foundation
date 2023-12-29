from foundation.types.component import Component, ComponentHead
from foundation.types.assembly import Assembly, AssemblyHead
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
from foundation.types.types import (
    FloatParameter,
    IntParameter,
    StringParameter,
    BoolParameter,
)
from foundation.rendering.material import Material

# TODO how do we enable the user to create nodes without touching this
# For now keeping track of the available nodes for serialization
# allows to catch errors on server side before sending to the frontend
# maybe versioning of the foundation lib can help here

serializable_nodes = {
    "Component": 0,
    "Assembly": 1,
    "Extrusion": 2,
    "Sketch": 3,
    "Point": 4,
    "PlaneFromFrame": 5,
    "Frame": 6,
    "OriginFrame": 7,
    "Line": 8,
    "FloatParameter": 9,
    "IntParameter": 10,
    "BoolParameter": 11,
    "StringParameter": 12,
    "SketchOrigin": 13,
    "ComponentHead": 14,
    "AssemblyHead": 15,
    "Circle": 16,
    "Rectangle": 17,
    "Square": 18,
    "Polygon": 19,
    "Hole": 20,
    "Material": 21,
    "Ellipse": 22,
    "Lathe": 23,
    "Axis": 24,
    "Hexagon": 25,
}
