from typing import Dict


# This is a dictionary that maps the name of the Serializable Nodes to
# a unique integer. This is used to serialize the DAG.
serializable_nodes: Dict[str, int] = {
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
