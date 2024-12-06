import math
from cadbuildr.foundation.geometry.tf_helper import get_rotation_matrix

from cadbuildr.foundation.types.node import Node
from cadbuildr.foundation.sketch.sketch import Point
from cadbuildr.foundation.sketch.primitives.line import Line
from cadbuildr.foundation.geometry.frame import Frame
from cadbuildr.foundation.types.node_children import NodeChildren


class AxisChildren(NodeChildren):
    line: Line
    frame: Frame


class Axis(Node):
    """Represents a special line that can serve as an axis for transformations."""

    children_class = AxisChildren

    def __init__(self, line: Line):
        """Initialize an Axis object.

        Args:
            line (Line): the line that will be the axis
        """
        Node.__init__(self, parents=[line.sketch])
        self.children.set_line(line)
        self.children.set_frame(line.sketch.frame)

        self.frame = self.children.frame
        self.line = self.children.line

        self.params = {}

    def get_axis_rotation(self) -> float:
        """Calculate the rotation angle of the axis compared to the y axis.

        Returns:
            float: the rotation angle in radians
        """
        p1, p2 = self.line.p1, self.line.p2
        x1, y1 = p1.x.value, p1.y.value
        x2, y2 = p2.x.value, p2.y.value
        return math.atan2(y2 - y1, x2 - x1)

    def get_axis_translation(self) -> float:
        """Calculate the distance from the origin to the axis.

        Returns:
            float: the distance from the origin to the axis
        """
        p1, p2 = self.line.p1, self.line.p2
        x1, y1 = p1.x.value, p1.y.value
        x2, y2 = p2.x.value, p2.y.value
        # distance to a line
        line_length = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        num = -(x2 - x1) * (y1) + (y2 - y1) * (x1)
        return num / line_length

    def get_axis_perpendicular_normed_vector(self) -> tuple[float, float]:
        """Calculate the normalized perpendicular vector to the axis line.

        Returns:
            tuple[float, float]: the normalized perpendicular vector
        """
        p1, p2 = self.line.p1, self.line.p2
        x1, y1 = p1.x.value, p1.y.value
        x2, y2 = p2.x.value, p2.y.value
        x = x2 - x1
        y = y2 - y1
        length = math.sqrt(x**2 + y**2)
        return y / length, -x / length

    def transform_point(self, point: Point) -> Point:
        """Transform a point based on the axis.

        Args:
            point (Point): The point to transform.

        Returns:
            Point: The transformed point.
        """
        if self.frame is None:
            self.get_new_frame()

        [x, y, _, _] = self.reversed_tf.dot([point.x.value, point.y.value, 0, 1])
        return Point(point.sketch, x, y)

    # TODO check if the function is end for type this because self.frame is not defined in __init__
    def get_new_frame(self):
        # TODO pydoc
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


AxisChildren.__annotations__["line"] = Line
AxisChildren.__annotations__["frame"] = Frame
