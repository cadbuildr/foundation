from cadbuildr.foundation.sketch.closed_sketch_shape import (
    Polygon,
    Circle,
    Ellipse,
    CustomClosedShape,
)
from cadbuildr.foundation.sketch.rectangle import Square, Rectangle
from cadbuildr.foundation.sketch.primitives.arc import Arc, EllipseArc
from cadbuildr.foundation.sketch.point import Point
import numpy as np

sketch_components = [
    Polygon,
    Circle,
    Square,
    Ellipse,
    Square,
    Rectangle,
    Arc,
    EllipseArc,
    CustomClosedShape,
]


class RectangularPattern:
    def __init__(self, width: float, height: float, n_rows: int, n_cols: int):
        self.width = width
        self.height = height
        self.n_rows = n_rows
        self.n_cols = n_cols

    def run(self, sketch_component):
        output = []
        if type(sketch_component) not in sketch_components:
            raise NotImplementedError(
                "Only support sketch component, {} is not supported".format(
                    type(sketch_component)
                )
            )

        for i in range(self.n_rows):
            row = []
            for j in range(self.n_cols):
                row.append(sketch_component.translate(self.width * j, self.height * i))
            output.append(row)
        return output


class CircularPattern:
    def __init__(self, center: Point, n_instances: int):
        self.center = center
        self.n_instances = n_instances

    def run(self, sketch_component):
        output = []
        if type(sketch_component) not in sketch_components:
            raise NotImplementedError(
                "Only support sketch component, {} is not supported".format(
                    type(sketch_component)
                )
            )

        d_angle = 2 * np.pi / self.n_instances
        for i in range(1, self.n_instances):
            output.append(sketch_component.rotate(i * d_angle, center=self.center))
        return output
