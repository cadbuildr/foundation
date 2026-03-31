"""Helper functions and methods for foundation API compatibility."""

from typing import Any, Iterable, Sequence

from .gen.models import (
    Part,
    Plane,
    Assembly,
    BoolParameter,
    Sketch,
    Point3D,
    Material,
    MaterialOptions,
)
from .gen.runtime import run_method
from .draw import Draw
from .constants import DEFAULT_COLORS


def _enable_auto_init(base_cls):
    """Ensure subclasses run BaseModel __init__ even if super().__init__ isn't called."""

    def _auto_init_subclass(cls, **kwargs):
        super(base_cls, cls).__init_subclass__(**kwargs)
        if cls is base_cls:
            return

        original_init = cls.__dict__.get("__init__")
        if original_init is None:
            return
        if getattr(original_init, "__foundation_auto_init__", False):
            return

        def wrapped_init(self, *args, **kwargs):
            # Initialize Pydantic fields with defaults (empty dict triggers default_factory)
            base_cls.__init__(self, **{})
            original_init(self, *args, **kwargs)

        wrapped_init.__foundation_auto_init__ = True  # type: ignore[attr-defined]
        cls.__init__ = wrapped_init  # type: ignore[assignment]

    base_cls.__init_subclass__ = classmethod(_auto_init_subclass)  # type: ignore[assignment]


_enable_auto_init(Part)
_enable_auto_init(Assembly)


class PlaneChildrenCompat:
    """Compatibility layer for Plane.children API (backward compatibility with old foundation)."""

    def __init__(self, plane: Plane):
        self._plane = plane

    def set_display(self, value: BoolParameter):
        """Set the display property of the plane."""
        self._plane.display = value


class PlaneFactory:
    """Factory for creating derived planes (for backward compatibility with old foundation API)."""

    def __init__(self):
        self.counter = 0

    def _get_name(self, name: str | None) -> str:
        if name is None:
            name = "plane_" + str(self.counter)
        self.counter += 1
        return name

    def get_parallel_plane(
        self, plane: Plane, distance: float, name: str | None = None
    ) -> Plane | None:
        """Create a plane parallel to the given plane at the given distance."""
        return plane.get_parallel_plane(distance=distance, name=self._get_name(name))

    def get_angle_plane_from_axis(
        self, plane: Plane, axis, angle: float, name: str | None = None
    ) -> Plane | None:
        """Create a plane rotated around the given axis by the given angle."""
        # Convert axis to list if it's a numpy array
        if hasattr(axis, "tolist"):
            axis = axis.tolist()
        elif not isinstance(axis, list):
            axis = list(axis)
        return plane.get_angle_plane_from_axis(
            axis=axis, angle=angle, name=self._get_name(name)
        )

    def get_plane_from_3_points(self, origin_frame, points, name: str | None = None):
        """Create a plane from 3 points.

        The frame will be oriented using [P1, P2] as the x axis and P1 as the origin.
        The frame arg is the coordinate system in which the points are defined.

        Args:
            origin_frame: Frame - the coordinate system in which the points are defined
            points: list[Point3D] - list of exactly three non-aligned Point3D objects
            name: str - optional name for the plane
        """
        import numpy as np
        from .gen.models import Plane, Frame, StringParameter, BoolParameter, Point3D
        from .math_utils import rotation_matrix_to_quaternion

        if len(points) != 3:
            raise ValueError("get_plane_from_3_points requires exactly 3 points")

        p1, p2, p3 = points

        # Create vectors from the points
        v1 = np.array(
            [p2.x.value - p1.x.value, p2.y.value - p1.y.value, p2.z.value - p1.z.value]
        )
        v2 = np.array(
            [p3.x.value - p1.x.value, p3.y.value - p1.y.value, p3.z.value - p1.z.value]
        )

        # Compute the normal to the plane
        normal = np.cross(v1, v2)
        if np.linalg.norm(normal) == 0:
            if np.linalg.norm(v1) == 0 or np.linalg.norm(v2) == 0:
                raise ValueError("At least two points are the same")
            raise ValueError("The points are aligned")
        normal /= np.linalg.norm(normal)

        # Create the frame using p1 as the origin and v1, v2 for the directions
        x_axis = v1 / np.linalg.norm(v1)
        y_axis = np.cross(normal, x_axis)
        y_axis /= np.linalg.norm(y_axis)

        if name is None:
            name = f"f_3dp_{self.counter}"

        # Create a Frame with origin p1 and axes x_axis, y_axis, normal
        origin = np.array([p1.x.value, p1.y.value, p1.z.value])

        # Form rotation matrix [x_axis, y_axis, normal] as columns
        rot_matrix = np.array([x_axis, y_axis, normal]).T

        # Convert to quaternion
        quaternion = rotation_matrix_to_quaternion(rot_matrix)

        # Create frame at p1 position with the computed orientation
        frame = Frame(
            top_frame=origin_frame,
            name=StringParameter(value=name),
            display=BoolParameter(value=False),
            position=origin.tolist(),
            quaternion=quaternion,
        )

        plane = Plane(frame=frame, name=StringParameter(value=f"p_3dp_{self.counter}"))
        self.counter += 1
        return plane


# Add children property to Plane for backward compatibility
def _plane_children_property(self):
    """Return compatibility layer for Plane.children API."""
    return PlaneChildrenCompat(self)


setattr(Plane, "children", property(_plane_children_property))


# Add pencil property to Sketch for backward compatibility
def _sketch_pencil_property(self):
    """Return Draw instance (pencil API) for Sketch."""
    pencil = getattr(self, "_pencil", None)
    if pencil is None:
        pencil = Draw(self)
        setattr(self, "_pencil", pencil)
    return pencil


setattr(Sketch, "pencil", property(_sketch_pencil_property))


# Add head property to Part for backward compatibility (head.frame, head._frame)
class PartHeadCompat:
    """Backward compatibility wrapper for Part.head API from old foundation."""

    def __init__(self, part: Part):
        self._part = part

    @property
    def _frame(self):
        """Access the frame (old foundation used _frame)."""
        return self._part.frame

    @property
    def frame(self):
        """Access the frame."""
        return self._part.frame


def _part_head_property(self):
    """Return compatibility layer for Part.head API."""
    head_compat = getattr(self, "_head_compat", None)
    if head_compat is None:
        head_compat = PartHeadCompat(self)
        setattr(self, "_head_compat", head_compat)
    return head_compat


setattr(Part, "head", property(_part_head_property))


# Add head property to Assembly for backward compatibility
class AssemblyHeadCompat:
    """Backward compatibility wrapper for Assembly.head API from old foundation."""

    def __init__(self, assembly: Assembly):
        self._assembly = assembly

    @property
    def _frame(self):
        """Access the frame (old foundation used _frame)."""
        return self._assembly.frame

    @property
    def frame(self):
        """Access the frame."""
        return self._assembly.frame


def _assembly_head_property(self):
    """Return compatibility layer for Assembly.head API."""
    head_compat = getattr(self, "_head_compat", None)
    if head_compat is None:
        head_compat = AssemblyHeadCompat(self)
        setattr(self, "_head_compat", head_compat)
    return head_compat


setattr(Assembly, "head", property(_assembly_head_property))


# Add set_diffuse_color method to Material for backward compatibility
def _material_set_diffuse_color(self, color):
    """Set the diffuse color on a Material (backward compatible API)."""
    if isinstance(color, str):
        if color not in DEFAULT_COLORS:
            raise ValueError(
                f"Unknown color '{color}'. Available colors: {list(DEFAULT_COLORS.keys())}"
            )
        diffuse_color = DEFAULT_COLORS[color]
    else:
        diffuse_color = list(color)
        if len(diffuse_color) != 3:
            raise ValueError("Diffuse color must have 3 components")

    self.options = MaterialOptions(diffuse_color=diffuse_color)
    return True


setattr(Material, "set_diffuse_color", _material_set_diffuse_color)


# Add set_material method to Part/Assembly for backward compatibility
def _set_component_material(self, material):
    """Attach a Material to a component for serialization."""
    object.__setattr__(self, "_material", material)
    return True


setattr(Part, "set_material", _set_component_material)
setattr(Assembly, "set_material", _set_component_material)


# TFHelper compatibility for legacy transform usage.
class TFHelper:
    def __init__(self) -> None:
        self._translation = [0.0, 0.0, 0.0]
        self._quaternion = [1.0, 0.0, 0.0, 0.0]

    @staticmethod
    def _as_list(value: Any, expected_len: int | None = None) -> list[float]:
        if hasattr(value, "tolist"):
            value = value.tolist()
        if isinstance(value, (list, tuple)):
            values = [float(item) for item in value]
            if expected_len is not None and len(values) != expected_len:
                raise ValueError(f"Expected {expected_len} values, got {len(values)}")
            return values
        raise TypeError("Transform values must be a list-like sequence")

    @classmethod
    def _parse_tf(cls, tf: Any) -> tuple[list[float] | None, list[float] | None]:
        if hasattr(tf, "get_tf") and callable(tf.get_tf):
            tf = tf.get_tf()
        if isinstance(tf, dict):
            translation = tf.get("translation") or tf.get("position")
            quaternion = tf.get("quaternion") or tf.get("rotation")
            return (
                cls._as_list(translation, 3) if translation is not None else None,
                cls._as_list(quaternion, 4) if quaternion is not None else None,
            )
        if isinstance(tf, (list, tuple)):
            if len(tf) == 3:
                return cls._as_list(tf, 3), None
            if len(tf) == 4 and all(isinstance(row, (list, tuple)) for row in tf):
                matrix = tf
            elif len(tf) == 16:
                matrix = [list(tf[i * 4 : i * 4 + 4]) for i in range(4)]
            else:
                return None, None
            import numpy as np
            from .math_utils import rotation_matrix_to_quaternion

            rot_matrix = np.array([row[:3] for row in matrix[:3]], dtype=float)
            translation = [
                float(matrix[0][3]),
                float(matrix[1][3]),
                float(matrix[2][3]),
            ]
            quaternion = rotation_matrix_to_quaternion(rot_matrix)
            return translation, quaternion
        return None, None

    def get_tf(self) -> dict[str, list[float]]:
        return {
            "translation": list(self._translation),
            "quaternion": list(self._quaternion),
        }

    def set_tf(self, tf: Any) -> "TFHelper":
        translation, quaternion = self._parse_tf(tf)
        if translation is not None:
            self._translation = translation
        if quaternion is not None:
            self._quaternion = quaternion
        return self

    def translate(self, translation: Iterable[float]) -> "TFHelper":
        vector = self._as_list(translation, 3)
        self._translation = [self._translation[i] + vector[i] for i in range(3)]
        return self

    def translate_x(self, distance: float) -> "TFHelper":
        return self.translate([distance, 0.0, 0.0])

    def translate_y(self, distance: float) -> "TFHelper":
        return self.translate([0.0, distance, 0.0])

    def translate_z(self, distance: float) -> "TFHelper":
        return self.translate([0.0, 0.0, distance])

    def rotate(self, axis: Sequence[float], angle: float) -> "TFHelper":
        from .math_utils import axis_angle_to_quaternion, quaternion_multiply

        rotation_quat = axis_angle_to_quaternion(self._as_list(axis, 3), angle)
        self._quaternion = quaternion_multiply(rotation_quat, self._quaternion)
        return self


def _assembly_add_component(self, component: Any, tf: Any = None):
    _locals = {"component": component, "tf": tf}
    return run_method(self, "add_component_method", _locals)


setattr(Assembly, "add_component", _assembly_add_component)


# Add to_array() method to Point3D for backward compatibility
def _point3d_to_array(self):
    """Convert the Point3D to a NumPy array."""
    import numpy as np

    return np.array([self.x.value, self.y.value, self.z.value])


setattr(Point3D, "to_array", _point3d_to_array)
