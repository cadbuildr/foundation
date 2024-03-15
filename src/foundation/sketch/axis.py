import math
from foundation.geometry.tf_helper import get_rotation_matrix
from itertools import count

from foundation.types.node import Node
from foundation.sketch.sketch import Sketch, Point
from foundation.sketch.line import Line


class Axis(Node):
    """a special line can be an axis #TODO is this general enough ?"""

    def __init__(self, line: Line):
        Node.__init__(self, parents=[line.sketch])
        self.register_child(line)
        self.sketch_frame = line.sketch.frame
        self.register_child(self.sketch_frame)
        self.params = {"n_line": line.id, "n_frame": self.sketch_frame.id}

    def get_axis_rotation(self) -> float:
        # return angle of rotation compared to the y axis
        p1, p2 = self.line.p1, self.line.p2
        x1, y1 = p1.x.value, p1.y.value
        x2, y2 = p2.x.value, p2.y.value
        return math.atan2(y2 - y1, x2 - x1)

    def get_axis_translation(self) -> float:
        # return the distance from the line to the origin
        p1, p2 = self.line.p1, self.line.p2
        x1, y1 = p1.x.value, p1.y.value
        x2, y2 = p2.x.value, p2.y.value
        # distance to a line
        line_length = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        num = -(x2 - x1) * (y1) + (y2 - y1) * (x1)
        return num / line_length

    def get_axis_perpendicular_normed_vector(self) -> tuple[float, float]:
        p1, p2 = self.line.p1, self.line.p2
        x1, y1 = p1.x.value, p1.y.value
        x2, y2 = p2.x.value, p2.y.value
        x = x2 - x1
        y = y2 - y1
        length = math.sqrt(x**2 + y**2)
        return y / length, -x / length

    def transform_point(self, point: Point) -> Point:
        """Default axis for lathe is the y axis, so we need to
        transform the points to translate and rotate them"""
        if self.frame is None:
            self.get_new_frame()

        [x, y, _, _] = self.reversed_tf.dot([point.x.value, point.y.value, 0, 1])
        return Point(point.sketch, x, y)

    # TODO check if the function is end for type this because self.frame is not defined in __init__
    def get_new_frame(self):
        # TODO create a new frame with the axis as the origin

        # translation
        # frame origin is the closest point to the previous origin on the axis.
        dist = self.get_axis_translation()
        vect = self.get_axis_perpendicular_normed_vector()

        dx, dy = dist * vect[0], dist * vect[1]
        # TODO unit test ?
        rot = self.get_axis_rotation()

        # rotation is along the z axis, y axis is 0 rotation.
        rot_mat = get_rotation_matrix([0, 0, 1], rot - math.pi / 2)
        frame = self.sketch_frame.get_rotate_then_translate_frame(
            name="axis_{}".format(self.id),
            translation=[dx, dy, 0],
            rotation=rot_mat,
        )
        self.frame = frame
        self.reversed_tf = self.frame.transform.inverse()
        # rotation
        return frame
