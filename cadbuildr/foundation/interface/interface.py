from __future__ import annotations

from cadbuildr.foundation.types.part import Part
from cadbuildr.foundation.types.assembly import Assembly

from typing import List, Callable
from cadbuildr.foundation.geometry.transform3d import TransformMatrix
import numpy as np
from numpy import ndarray

from cadbuildr.foundation.geometry.tf_helper import TFHelper


class Interface:
    """A (Mechanical) inteface represents a way for multiple parts to interact with each other.
    It has a name
    """

    SPECS: List[Spec] = []

    def __init__(self):
        self.constraints: List[Constraints] = []
        for spec in self.SPECS:
            # check if the name is already taken
            if hasattr(self, spec.name):
                raise ValueError(f"Interface already has a spec named {spec.name}")
            setattr(self, spec.name, spec)

    def add_constraint(self, constraint: Constraints):
        self.constraints.append(constraint)

    def apply_constraints(self, top_assy: Assembly):
        """Apply all constraints associated with this interface."""
        for constraint in self.constraints:
            constraint.apply(top_assy)


class Spec:
    """A spec encompass a key dimensions, and patterns. They can be used
    for individual parts or for interfaces between parts

    some of the specs can have a apply function that can be used to apply the spec to
    - a part/assy
    - a plane or a sketch

    """

    def __init__(self, name: str):
        self.name = name


class DistanceSpec(Spec):
    """A distance specification between two points"""

    def __init__(self, name: str, value: float):
        self.value = value
        self.name = name

    def __mul__(self, other):
        if isinstance(other, (int, float)):
            return self.value * other
        raise TypeError(
            f"unsupported operand type(s) for *: '{type(self).__name__}' and '{type(other).__name__}'"
        )

    def __rmul__(self, other):
        return self.__mul__(other)

    def __add__(self, other):
        if isinstance(other, (int, float)):
            return self.value + other
        if isinstance(other, DistanceSpec):
            return self.value + other.value
        raise TypeError(
            f"unsupported operand type(s) for +: '{type(self).__name__}' and '{type(other).__name__}'"
        )

    def __radd__(self, other):
        return self.__add__(other)

    def __sub__(self, other):
        if isinstance(other, (int, float)):
            return self.value - other
        if isinstance(other, DistanceSpec):
            return self.value - other.value
        raise TypeError(
            f"unsupported operand type(s) for -: '{type(self).__name__}' and '{type(other).__name__}'"
        )

    def __rsub__(self, other):
        if isinstance(other, (int, float)):
            return other - self.value
        raise TypeError(
            f"unsupported operand type(s) for -: '{type(other).__name__}' and '{type(self).__name__}'"
        )

    def __truediv__(self, other):
        if isinstance(other, (int, float)):
            return self.value / other
        raise TypeError(
            f"unsupported operand type(s) for /: '{type(self).__name__}' and '{type(other).__name__}'"
        )

    def __rtruediv__(self, other):
        if isinstance(other, (int, float)):
            return other / self.value
        raise TypeError(
            f"unsupported operand type(s) for /: '{type(other).__name__}' and '{type(self).__name__}'"
        )

    def __repr__(self):
        return f"DistanceSpec('{self.name}', {self.value})"


class PatternSpec(Spec):
    """A pattern specification for a part or an interface"""

    def __init__(self, name: str):
        self.name = name

    def apply(self, applicator: Callable):
        raise NotImplementedError("This method should be implemented by the subclass")


class RectangularPatternSpec(PatternSpec):
    """A pattern based on a rectangular grid"""

    def __init__(
        self,
        name: str,
        x_spacing: DistanceSpec,
        y_spacing: DistanceSpec,
        n_x: int,
        n_y: int,
    ):
        self.x_spacing = x_spacing
        self.y_spacing = y_spacing
        self.n_x = n_x
        self.n_y = n_y
        super().__init__(name)

    def apply(self, applicator: Callable):
        """applicator is a function that takes x and y as input"""
        results = []
        for i in range(self.n_x):
            for j in range(self.n_y):
                results.append(
                    applicator(i * self.x_spacing.value, j * self.y_spacing.value)
                )
        return results


class RowPatternSpec(RectangularPatternSpec):
    """A pattern based on a row"""

    def __init__(self, name: str, spacing: DistanceSpec, n: int):
        super().__init__(name, spacing, DistanceSpec("0", 0), n, 1)


class AngularPatternSpec(PatternSpec):
    """A pattern based on an angle"""

    def __init__(self, name: str, start_angle: float, end_angle: float, n: int):
        self.start_angle = start_angle
        self.end_angle = end_angle
        self.n = n
        super().__init__(name)

    def apply(self, applicator: Callable):
        results = []
        d_angle = (self.end_angle - self.start_angle) / self.n
        for i in range(self.n):
            x = np.cos(self.start_angle + i * d_angle)
            y = np.sin(self.start_angle + i * d_angle)
            results.append(applicator(x, y))
        return results


class FullCircularPatternSpec(AngularPatternSpec):
    """A pattern based on a full circle"""

    def __init__(self, name: str, n: int):
        self.n = n
        super().__init__(name, 0, 2 * np.pi, n)


class ShapeRectangularPatternSpec(RectangularPatternSpec):
    def __init__(self):
        pass

    # def apply(plane: Plane):
    #     # create sketch and apply pattern returns the sketch.
    #     # TODO
    #     pass


class Constraints:
    """A (geometry) constraint is a rule that can be applied from a part/assembly to another part(s)/assembly(s)
    to constrain their position or orientation"""

    def __init__(
        self,
        parent: Part | Assembly | None = None,
        children: List[Part | Assembly] = [],
    ):
        self.parent = parent
        self.children = children

    def apply(self, top_assy: Assembly):
        """Apply the constraint to the top assembly"""
        raise NotImplementedError("This method should be implemented by the subclass")


class SingleChildConstraint(Constraints):
    """A constraint that applies to a single child"""

    def __init__(self, parent: Part | Assembly | None, child: Part | Assembly):
        super().__init__(parent, [child])
        self.child = child


class AnchorConstraint(SingleChildConstraint):
    def __init__(self, child: Part | Assembly, tf: TransformMatrix):
        super().__init__(None, child)
        self.tf = tf

    def apply(self, top_assy: Assembly):
        top_assy.add_component(self.child, self.tf)


class AnchorTranslationConstraint(SingleChildConstraint):
    def __init__(self, child: Part | Assembly, translation: np.ndarray):
        """translation is [x,y,z]"""
        super().__init__(None, child)
        self.translation = translation

    def apply(self, top_assy: Assembly):
        """add the child in the assy with the right position"""
        self.child.translate(self.translation)
        top_assy.add_component(self.child)


class FixedConstraint(SingleChildConstraint):
    def __init__(
        self,
        parent: Part | Assembly,
        child: Part | Assembly,
        tf: TransformMatrix | None = None,
    ):
        super().__init__(parent, child)
        if tf is None:
            tf = TransformMatrix.get_identity()
        self.tf = tf

    def apply(self, top_assy: Assembly):
        # Important to add the component before the frame parent change
        # because the frame is named "origin" by default otherwise.
        top_assy.add_component(self.child)
        if self.parent is not None:
            self.child.head.get_frame().change_top_frame(
                self.parent.head.get_frame(), new_tf=self.tf
            )


class FixedTranslationConstraint(FixedConstraint):
    def __init__(
        self,
        parent: Part | Assembly,
        child: Part | Assembly,
        translation: np.ndarray,
    ):
        super().__init__(parent, child, TFHelper().translate(translation).get_tf())


class FixedRotationConstraint(FixedConstraint):
    """A fixed rotation constraint that rotates the child relative to the parent."""

    def __init__(
        self, parent: Assembly, child: Part | Assembly, angle: float, axis: ndarray
    ):
        super().__init__(parent, child, TFHelper().rotate(axis, angle).get_tf())
