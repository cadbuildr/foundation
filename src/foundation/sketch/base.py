from foundation.types.node_interface import NodeInterface
from foundation.geometry.frame import Frame
from foundation.geometry.plane import PlaneFromFrame


""" File with code to produce (2D) sketches on planes
This is largely inspired by shapely and provides an interface to
the library """


class SketchShape(NodeInterface):
    def __init__(self, sketch: "Sketch"):
        super().__init__()
        # not sure if this is the best way to do this
        # we could have diferent frames on a sketchshape,
        # but this is the easiest way to do it for now
        # TODO when dealing with 2d transform and multiple frames in a plane ->
        # change it.
        self.sketch = sketch

    # TODO check what is the plane to use
    def get_plane(self) -> PlaneFromFrame:
        return self.sketch.plane

    def get_frame(self) -> Frame:
        return self.sketch.plane.frame
