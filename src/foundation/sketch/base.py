from foundation.types.node_interface import NodeInterface


""" File with code to produce (2D) sketches on planes
This is largely inspired by shapely and provides an interface to
the library """


class SketchShape(NodeInterface):
    def __init__(self, sketch):
        super().__init__()
        # not sure if this is the best way to do this
        # we could have diferent frames on a sketchshape,
        # but this is the easiest way to do it for now
        # TODO when dealing with 2d transform and multiple frames in a plane ->
        # change it.
        self.sketch = sketch

    def get_plane(self):
        return self.sketch.plane

    def get_frame(self):
        return self.sketch.plane.frame
