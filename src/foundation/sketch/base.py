from foundation.types.node_interface import NodeInterface
from foundation.geometry.frame import Frame
from foundation.geometry.plane import Plane

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from foundation.sketch.sketch import Sketch


class SketchElement(NodeInterface):
    def __init__(self, sketch: "Sketch"):
        super().__init__()
        self.sketch = sketch

    # TODO check what is the plane to use
    def get_plane(self) -> Plane:
        return self.sketch.plane

    def get_frame(self) -> Frame:
        return self.sketch.plane.frame


class SketchPrimitives(SketchElement):
    """A NodeInterface for element that combined together can form a
    closed shape, for instance :
    - lines,
    - arcs,
    - EllipseArc ..."""

    def __init__(self, sketch: "Sketch"):
        super().__init__(sketch)

    def get_points(self) -> list:
        raise NotImplementedError("Implement in children")
