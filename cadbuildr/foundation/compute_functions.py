"""Compute functions for foundation schema directives."""

from typing import Any, Callable, Iterable, Optional, Sequence
import math

from .gen.runtime import register_compute_fn, register_method_fn
from .gen.models import (
    Arc,
    Plane,
    Frame,
    StringParameter,
    BoolParameter,
    FloatParameter,
    Point,
    Sketch,
    Part,
    PartRoot,
    Assembly,
    AssemblyRoot,
)
from .helpers import PlaneFactory
from .constants import DEFAULT_COLORS, PLANES_CONFIG
from .math_utils import (
    quaternion_to_axes,
    axis_angle_to_quaternion,
    quaternion_multiply,
    create_frame_from_xdir_and_normal,
)


@register_compute_fn("get_plane_factory")
def get_plane_factory(inst: Any, field_name: str, meta: dict[str, Any]) -> PlaneFactory:
    """Get a PlaneFactory instance for creating derived planes."""
    return PlaneFactory()


@register_compute_fn("get_sketch_origin")
def get_sketch_origin(inst: Sketch, field_name: str, meta: dict[str, Any]) -> Point:
    """Get the origin point of a sketch from its plane."""
    return Point(sketch=inst, x=FloatParameter(value=0.0), y=FloatParameter(value=0.0))


@register_compute_fn("compute_arc_control_point")
def compute_arc_control_point(inst: Arc, field_name: str, meta: dict[str, Any]) -> Point:
    """Compute the control point (p2) for an arc from two points and radius.

    Based on old foundation implementation in arc.py:from_two_points_and_radius
    The arc is on the left side of the line from p1 to p2 when radius is positive.
    """
    p1 = inst.p1
    p2 = inst.p2
    radius_value = inst.radius.value
    sketch = inst.sketch

    # Calculate midpoint
    midpoint_x = (p1.x.value + p2.x.value) / 2
    midpoint_y = (p1.y.value + p2.y.value) / 2

    # Calculate distance between the points
    distance = math.sqrt(
        (p2.x.value - p1.x.value) ** 2 + (p2.y.value - p1.y.value) ** 2
    )

    if distance == 0:
        raise ValueError("The distance between the arc endpoints is zero")

    if distance > 2 * abs(radius_value):
        raise ValueError(
            f"The distance between points ({distance}) is greater than the diameter "
            f"of the circle (2 * {abs(radius_value)} = {2 * abs(radius_value)})"
        )

    # Calculate the direction perpendicular to the line segment
    dx = (p2.y.value - p1.y.value) / distance
    dy = -(p2.x.value - p1.x.value) / distance

    # Calculate offset from midpoint to control point
    # (p1, midpoint, center) forms a right triangle
    d = abs(radius_value) - math.sqrt(radius_value**2 - (distance / 2) ** 2)

    sign = math.copysign(1, radius_value)

    # Compute control point (on the arc, perpendicular to midpoint)
    control_x = midpoint_x - d * dx * sign
    control_y = midpoint_y - d * dy * sign

    return Point(
        sketch=sketch,
        x=FloatParameter(value=control_x),
        y=FloatParameter(value=control_y),
    )


@register_method_fn("add_element_method")
def add_element_method(inst: Sketch, element: Any) -> bool:
    """Add an element to the sketch's elements list."""
    # Initialize elements if it doesn't exist (though Pydantic should handle this)
    if not hasattr(inst, "elements") or inst.elements is None:
        inst.elements = []

    # Add element if not already present
    if element not in inst.elements:
        inst.elements.append(element)

    return True


@register_compute_fn("get_extrusion_sketch")
def get_extrusion_sketch(inst: Any, field_name: str, meta: dict[str, Any]) -> Sketch:
    """Get the sketch for an extrusion from its shape."""
    # The sketch is derived from the first shape's sketch attribute
    # shape is a list, so we get the first element
    if not inst.shape or len(inst.shape) == 0:
        raise ValueError("Extrusion must have at least one shape")

    first_shape = inst.shape[0]
    if hasattr(first_shape, "sketch"):
        sketch = first_shape.sketch
        # If sketch is None, try to compute it
        if sketch is None and hasattr(first_shape, "compute"):
            sketch = first_shape.compute("sketch")
        return sketch
    raise ValueError(f"Shape {first_shape} does not have a sketch attribute")


@register_compute_fn("compute_loft_sketches")
def compute_loft_sketches(
    inst: Any, field_name: str, meta: dict[str, Any]
) -> list[Sketch]:
    """Compute the list of sketches from the loft shapes."""
    sketches = []
    for shape in inst.shapes:
        if hasattr(shape, "sketch"):
            sketch = shape.sketch
            # If sketch is None, try to compute it
            if sketch is None and hasattr(shape, "compute"):
                sketch = shape.compute("sketch")
            if sketch is not None:
                sketches.append(sketch)
    return sketches


@register_compute_fn("compute_sweep_sketch")
def compute_sweep_sketch(inst: Any, field_name: str, meta: dict[str, Any]) -> Sketch:
    """Compute the sketch used by a sweep operation from its profile."""
    profile = inst.profile
    if hasattr(profile, "sketch"):
        sketch = profile.sketch
        if sketch is None and hasattr(profile, "compute"):
            sketch = profile.compute("sketch")
        if sketch is not None:
            return sketch
    raise ValueError(f"Profile {profile} does not provide a valid sketch for Sweep")


@register_compute_fn("compute_thread_path")
def compute_thread_path(inst: Any, field_name: str, meta: dict[str, Any]) -> Any:
    """Compute the helix path used by a thread macro node."""
    from .gen.models import Helix3D

    return Helix3D(
        pitch=inst.pitch,
        height=inst.height,
        radius=inst.radius,
        center=inst.center,
        dir=inst.dir,
        lefthand=inst.lefthand,
    )


def _create_plane_method(
    plane_name: str,
    config: tuple[list[int], list[int]] | None,
) -> Callable[[Any], Plane]:
    """Create a plane method function for a given plane name and configuration."""

    def plane_method(inst: Part) -> Plane:
        """Get a plane from a part's frame."""
        # Check if plane already exists in the planes list
        for existing_plane in inst.planes:
            plane_name_param = existing_plane.name
            if (
                hasattr(plane_name_param, "value")
                and plane_name_param.value == plane_name
            ):
                return existing_plane

        # Create new plane
        if config is None:
            # Special case: XY plane uses the part's frame directly
            plane = Plane(
                frame=inst.frame,
                name=StringParameter(value=plane_name),
                display=BoolParameter(value=False),
            )
        else:
            # Other planes: create frame with specific orientation
            x_dir, normal = config
            new_frame = create_frame_from_xdir_and_normal(
                inst.frame,
                x_dir,
                normal,
                f"{plane_name}_frame",  # Add "_frame" suffix to avoid name collision with plane
            )
            plane = Plane(
                frame=new_frame,
                name=StringParameter(value=plane_name),
                display=BoolParameter(value=False),
            )

        # Register the plane with the part
        inst.planes.append(plane)
        return plane

    # Set docstring
    plane_method.__doc__ = f"Get the {plane_name.upper()} plane from a part's frame."
    return plane_method


# Dynamically register all plane methods
for plane_name, config in PLANES_CONFIG.items():
    method_name = f"get_{plane_name}_plane"
    method_fn = _create_plane_method(plane_name, config)
    register_method_fn(method_name)(method_fn)


@register_method_fn("get_origin_planes_method")
def get_origin_planes_method(inst: Part | Assembly) -> list[Plane]:
    """Get the three main origin planes (xy, xz, yz) as a list."""
    return [inst.xy(), inst.xz(), inst.yz()]


@register_method_fn("add_operation_method")
def add_operation_method(inst: Part, operation: Any) -> bool:
    """Add an operation to a part."""
    from .gen.runtime import Expandable

    # If the operation is expandable (like Hole), expand it first
    if isinstance(operation, Expandable):
        operation = operation.expand()

    inst.operations.append(operation)
    return True


@register_method_fn("add_operations_method")
def add_operations_method(inst: Part, operations: Iterable[Any]) -> bool:
    """Add multiple operations to a part at once."""
    from .gen.runtime import Expandable

    for operation in operations:
        # If the operation is expandable (like Hole), expand it first
        if isinstance(operation, Expandable):
            operation = operation.expand()
        inst.operations.append(operation)
    return True


@register_method_fn("interface_grid_offset_method")
def interface_grid_offset_method(
    inst: Any, n_x: int = 0, n_y: int = 0, n_z: int = 0
) -> list[float]:
    """Compute a translation vector from integer grid offsets."""
    return [
        float(n_x) * float(inst.pitch_x.value),
        float(n_y) * float(inst.pitch_y.value),
        float(n_z) * float(inst.pitch_z.value),
    ]


@register_method_fn("interface_add_constraint_method")
def interface_add_constraint_method(
    inst: Any,
    component: Any,
    translation: Sequence[float],
    quaternion: Sequence[float] = (1.0, 0.0, 0.0, 0.0),
) -> bool:
    """Append a translation/quaternion-based placement constraint."""
    from .gen.models import FixedTranslationConstraint

    vector = _normalize_vector(translation, 3)
    quat = _normalize_vector(quaternion, 4)
    inst.constraints.append(
        FixedTranslationConstraint(component=component, translation=vector, quaternion=quat)
    )
    return True


@register_method_fn("interface_place_method")
def interface_place_method(
    inst: Any, component: Any, n_x: int = 0, n_y: int = 0, n_z: int = 0
) -> bool:
    """Place a component using this interface's grid spacing."""
    offset = inst.grid.offset(n_x=n_x, n_y=n_y, n_z=n_z)
    return inst.add_constraint(component=component, translation=offset)


@register_method_fn("interface_clip_method")
def interface_clip_method(
    inst: Any, component: Any, n_x: int = 0, n_y: int = 0, n_z: int = 1
) -> bool:
    """Convenience method to place one level above the current grid by default."""
    return interface_place_method(inst, component=component, n_x=n_x, n_y=n_y, n_z=n_z)


@register_method_fn("interface_apply_method")
def interface_apply_method(inst: Any, assembly: Any) -> bool:
    """Apply all stored constraints to the provided assembly."""
    for constraint in inst.constraints:
        assembly.add_component(
            constraint.component,
            tf={
                "translation": list(constraint.translation),
                "quaternion": list(constraint.quaternion),
            },
        )
    return True


# Counters for unique naming
_material_counter = 0


@register_method_fn("paint_method")
def paint_method(inst: Part | Assembly, color: str, transparency: float = 0.5) -> bool:
    """Paint a part (creates Material instance)."""
    global _material_counter
    from .gen.models import Material, MaterialOptions

    # Get RGB color from name
    if color not in DEFAULT_COLORS:
        raise ValueError(
            f"Unknown color '{color}'. Available colors: {list(DEFAULT_COLORS.keys())}"
        )

    diffuse_color = DEFAULT_COLORS[color]

    # Create Material instance
    _material_counter += 1
    material = Material(
        name=f"Material_{_material_counter}",
        painted_node_ids=[],
        options=MaterialOptions(diffuse_color=diffuse_color, transparency=float(transparency)),
    )

    # Store material on instance
    object.__setattr__(inst, "_material", material)
    return True


@register_method_fn("translate_method")
def translate_method(inst: Part | Assembly, translation: Sequence[float]) -> bool:
    """Translate a part or assembly by updating its frame position.

    For assemblies, only the assembly's frame is moved. Child components don't need
    updating because their frames are relative to the assembly frame.
    """
    if len(translation) != 3:
        raise ValueError("Translation vector must have exactly 3 components")
    vector = [float(translation[i]) for i in range(3)]
    inst.frame.position = [inst.frame.position[i] + vector[i] for i in range(3)]
    return True


@register_method_fn("translate_x_method")
def translate_x_method(inst: Part | Assembly, x: float) -> bool:
    """Translate a part or assembly along the X axis."""
    return translate_method(inst, [x, 0.0, 0.0])


@register_method_fn("translate_y_method")
def translate_y_method(inst: Part | Assembly, y: float) -> bool:
    """Translate a part or assembly along the Y axis."""
    return translate_method(inst, [0.0, y, 0.0])


@register_method_fn("translate_z_method")
def translate_z_method(inst: Part | Assembly, z: float) -> bool:
    """Translate a part or assembly along the Z axis."""
    return translate_method(inst, [0.0, 0.0, z])


@register_method_fn("rotate_method")
def rotate_method(inst: Part | Assembly, angle: float, axis: Sequence[float] = (0.0, 0.0, 1.0)) -> bool:
    """Rotate a part or assembly around an axis by updating its frame quaternion.

    Args:
        angle: Rotation angle in radians
        axis: Rotation axis (default: [0, 0, 1] for Z-axis rotation)
    """
    # Backward compatibility: allow rotate(axis, angle) call signature.
    if isinstance(axis, (int, float)) and hasattr(angle, "__len__"):
        angle, axis = axis, angle
    if len(axis) != 3:
        raise ValueError("Axis vector must have exactly 3 components")

    # Convert axis-angle to quaternion
    rotation_quat = axis_angle_to_quaternion(axis, angle)

    # Multiply: new_quat = rotation_quat * current_quat (apply rotation)
    inst.frame.quaternion = quaternion_multiply(rotation_quat, inst.frame.quaternion)

    # Note: For assemblies, we only rotate the assembly frame
    # Child components will follow since their frames reference the assembly frame
    return True


@register_method_fn("to_dag_method")
def to_dag_method(
    inst: Part | Assembly, memo: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Convert Part or Assembly to raw DAG dictionary (not formatted with version/rootNodeId)."""
    from .foundation_hooks import setup_foundation_hooks
    from .gen.dag import pydantic_to_dag
    from .constants import DEFAULT_TYPE_REGISTRY

    if memo is None:
        memo = {}

    hooks = setup_foundation_hooks()
    type_registry = DEFAULT_TYPE_REGISTRY.copy()

    # Convert to root if needed
    from .compute_functions import _convert_component_to_root

    if isinstance(inst, (Part, Assembly)):
        inst = _convert_component_to_root(inst)

    pydantic_to_dag(inst, memo, type_registry, hooks)

    # Return raw memo dictionary (like old foundation)
    return memo


def make_origin_frame_default_frame(
    frame: Frame, component_id: str, new_top_frame: Optional[Frame]
) -> None:
    """Update a component's origin frame to point to a parent frame.

    This mimics the old foundation's behavior where component frames are updated
    in place. Planes that reference this frame will automatically follow the updated hierarchy.

    CRITICAL: When a frame gets a new top_frame, its position must be reset to [0,0,0]
    because positions are RELATIVE to the parent frame. The frontend will add the parent's
    position, so keeping the absolute position would double the translation!

    Args:
        frame: The component's frame (typically named "origin") - updated in place
        component_id: Unique identifier for the component
        new_top_frame: The parent frame (assembly frame) to point to
    """
    from .gen.models import StringParameter

    # Update the frame's top_frame in place (like old foundation's change_top_frame)
    if new_top_frame is not None:
        frame.top_frame = new_top_frame

    # NOTE: We do NOT reset position here!
    # If the user called translate() on the Part before add_component(),
    # that position represents the Part's position RELATIVE to its parent.
    # The frame.position should be kept as-is.

    # Update frame name if it's still "origin"
    if frame.name.value == "origin":
        frame.name = StringParameter(value=f"{component_id}_origin")


def _format_component_path(path: tuple[int, ...]) -> str:
    if not path:
        return "root"
    return "_".join(str(i) for i in path)


def _convert_component_to_root(
    component: Any,
    parent_frame: Optional[Frame] = None,
    component_path: tuple[int, ...] = (),
) -> Optional[PartRoot | AssemblyRoot]:
    """Convert Part/Assembly instances to their root representations.

    Args:
        component: Part or Assembly to convert
        parent_frame: Optional parent frame (assembly frame) that component frame should point to
    """
    from .gen.models import Frame, StringParameter, BoolParameter

    if isinstance(component, PartRoot):
        # Component is already a PartRoot, but we may need to update its frame's top_frame
        if parent_frame is not None and component.frame.top_frame != parent_frame:
            # Update the frame's top_frame to point to parent
            component.frame.top_frame = parent_frame
        return component
    if isinstance(component, AssemblyRoot):
        # Component is already an AssemblyRoot, recursively update its components
        if parent_frame is not None:
            # Update this assembly's frame's top_frame
            component.frame.top_frame = parent_frame
            # Recursively update nested components
            for idx, child in enumerate(component.components):
                _convert_component_to_root(
                    child,
                    parent_frame=component.frame,
                    component_path=component_path + (idx,),
                )
        return component
    if isinstance(component, Part):
        # Update the component's frame to point to parent_frame (like old foundation)
        # This is all we need - planes that reference component.frame will automatically follow
        component_id = f"component_{_format_component_path(component_path)}"
        make_origin_frame_default_frame(
            component.frame,
            component_id,
            parent_frame if parent_frame is not None else component.frame.top_frame,
        )

        # Generate deterministic name if still using default 'part0'.
        # This avoids process-global counter side effects in DAG hashing.
        part_name = component.name
        if part_name.value == "part0":
            part_name = StringParameter(
                value=f"part_{_format_component_path(component_path)}"
            )

        return PartRoot(
            frame=component.frame,  # Use the updated frame (updated in place)
            name=part_name,
            operations=component.operations,  # No need to update - frames reference component.frame which we just updated
            planes=component.planes,  # No need to update - frames reference component.frame which we just updated
            material=getattr(component, "_material", None),
        )
    if isinstance(component, Assembly):
        # Create assembly frame first
        original_frame = component.frame
        unique_frame_name = (
            f"assembly_{_format_component_path(component_path)}_frame"
        )

        # KEEP the assembly's position - it represents the transform applied to this assembly
        assembly_frame = Frame(
            top_frame=original_frame.top_frame
            if parent_frame is None
            else parent_frame,
            name=StringParameter(value=unique_frame_name),
            display=BoolParameter(value=original_frame.display.value),
            position=original_frame.position.copy()
            if isinstance(original_frame.position, list)
            else original_frame.position,
            quaternion=original_frame.quaternion.copy()
            if isinstance(original_frame.quaternion, list)
            else original_frame.quaternion,
        )

        # RECURSIVELY convert nested components, passing assembly frame so component frames can point to it
        converted_components = []
        for idx, c in enumerate(component.components):
            converted = _convert_component_to_root(
                c,
                parent_frame=assembly_frame,
                component_path=component_path + (idx,),
            )
            converted_components.append(converted)

        # Generate deterministic assembly name if still using default 'assembly0'.
        assembly_name = component.name
        if assembly_name.value == "assembly0":
            assembly_name = StringParameter(
                value=f"assy_{_format_component_path(component_path)}"
            )

        return AssemblyRoot(
            frame=assembly_frame,
            name=assembly_name,
            components=converted_components,
            material=getattr(component, "_material", None),
        )


def _translate_component_root(component_root: Any, vector: Sequence[float]) -> None:
    """Apply translation to component roots recursively."""
    if isinstance(component_root, PartRoot):
        component_root.frame.position = [
            component_root.frame.position[i] + vector[i] for i in range(3)
        ]
        return
    if isinstance(component_root, AssemblyRoot):
        component_root.frame.position = [
            component_root.frame.position[i] + vector[i] for i in range(3)
        ]
        for child in component_root.components:
            _translate_component_root(child, vector)
        return
    raise TypeError(
        f"Unsupported component type '{type(component_root).__name__}' for translation"
    )


@register_method_fn("add_component_method")
def add_component_method(inst: Assembly, component: Any, tf: Any = None) -> bool:
    """Add a component (part or assembly) to an assembly."""
    # Pass the assembly's frame as parent so child frames become relative to it
    component_root = _convert_component_to_root(component, parent_frame=inst.frame)
    translation, quaternion = _parse_component_tf(tf)
    if translation is not None:
        _apply_translation_to_root(component_root, translation)
    if quaternion is not None:
        _apply_rotation_to_root(component_root, quaternion)
    inst.components.append(component_root)
    return True


def _apply_translation_to_root(component_root: Any, vector: Sequence[float]) -> None:
    component_root.frame.position = [
        component_root.frame.position[i] + vector[i] for i in range(3)
    ]


def _apply_rotation_to_root(component_root: Any, quaternion: Sequence[float]) -> None:
    component_root.frame.quaternion = quaternion_multiply(
        list(quaternion), component_root.frame.quaternion
    )


def _parse_component_tf(tf: Any) -> tuple[list[float] | None, list[float] | None]:
    if tf is None:
        return None, None
    if hasattr(tf, "get_tf") and callable(tf.get_tf):
        tf = tf.get_tf()
    if isinstance(tf, dict):
        translation = tf.get("translation") or tf.get("position")
        quaternion = tf.get("quaternion") or tf.get("rotation")
        return (
            _normalize_vector(translation, 3) if translation is not None else None,
            _normalize_vector(quaternion, 4) if quaternion is not None else None,
        )
    if isinstance(tf, (list, tuple)):
        if len(tf) == 3:
            return _normalize_vector(tf, 3), None
        matrix: list[list[float]] | None = None
        if len(tf) == 4 and all(isinstance(row, (list, tuple)) for row in tf):
            matrix = [list(row) for row in tf]
        elif len(tf) == 16:
            matrix = [list(tf[i * 4 : i * 4 + 4]) for i in range(4)]
        if matrix is not None:
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


def _normalize_vector(value: Any, expected_len: int) -> list[float]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, (list, tuple)):
        raise TypeError("Transform values must be a list-like sequence")
    values = [float(item) for item in value]
    if len(values) != expected_len:
        raise ValueError(f"Expected {expected_len} values, got {len(values)}")
    return values


@register_method_fn("get_parallel_plane_method")
def get_parallel_plane_method(inst: Plane, distance: float, name: str = "parallel") -> Plane:
    """Create a plane parallel to this plane at given distance."""
    # Get normal vector from frame's Z-axis (quaternion's up direction)
    # Quaternion format: [w, x, y, z]
    q = inst.frame.quaternion
    w, x, y, z = q[0], q[1], q[2], q[3]

    # Convert quaternion to rotation matrix and extract Z-axis (normal)
    # Z-axis is the third column of the rotation matrix
    normal_x = 2 * (x * z + w * y)
    normal_y = 2 * (y * z - w * x)
    normal_z = 1 - 2 * (x * x + y * y)

    # Translate frame position along the normal
    new_position = [
        inst.frame.position[0] + normal_x * distance,
        inst.frame.position[1] + normal_y * distance,
        inst.frame.position[2] + normal_z * distance,
    ]

    return Plane(
        frame=Frame(
            top_frame=inst.frame,
            name=StringParameter(value=f"frame_{name}"),
            display=BoolParameter(value=False),
            position=new_position,
            quaternion=inst.frame.quaternion,  # Same orientation
        ),
        name=StringParameter(value=name),
        display=BoolParameter(value=False),
    )


@register_method_fn("get_plane_x_axis")
def get_plane_x_axis(inst: Plane) -> list[float]:
    """Get the X-axis of the plane's frame."""
    x_axis, _, _ = quaternion_to_axes(inst.frame.quaternion)
    return x_axis


@register_method_fn("get_plane_y_axis")
def get_plane_y_axis(inst: Plane) -> list[float]:
    """Get the Y-axis of the plane's frame."""
    _, y_axis, _ = quaternion_to_axes(inst.frame.quaternion)
    return y_axis


@register_method_fn("get_plane_z_axis")
def get_plane_z_axis(inst: Plane) -> list[float]:
    """Get the Z-axis of the plane's frame."""
    _, _, z_axis = quaternion_to_axes(inst.frame.quaternion)
    return z_axis


@register_method_fn("get_angle_plane_from_axis_method")
def get_angle_plane_from_axis_method(
    inst: Plane, axis: Sequence[float], angle: float, name: str = "rotated"
) -> Plane:
    """Create a plane rotated around the given axis by the given angle."""
    # Convert axis-angle to quaternion
    rotation_quat = axis_angle_to_quaternion(axis, angle)

    # Multiply quaternions: new_quat = rotation_quat * original_quat
    new_quaternion = quaternion_multiply(rotation_quat, inst.frame.quaternion)

    return Plane(
        frame=Frame(
            top_frame=inst.frame,
            name=StringParameter(value=f"frame_{name}"),
            display=BoolParameter(value=False),
            position=[
                0.0,
                0.0,
                0.0,
            ],  # No translation, just rotation (position is relative to parent)
            quaternion=new_quaternion,  # New orientation
        ),
        name=StringParameter(value=name),
        display=BoolParameter(value=False),  # Don't display construction planes
    )
