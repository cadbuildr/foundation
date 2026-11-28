"""Assembly patterns: linear / polar patterns and replicate of a component.

Onshape's assembly "Linear pattern", "Circular pattern" and "Replicate"::

    bolts = flange_assy.polar_pattern(bolt, 6)                 # about +Z
    rollers = conveyor.linear_pattern(roller, (1, 0, 0), 8, 40.0)
    pins = plate_assy.replicate(Pin(), onto=holes, child_anchor="foot")

Every copy is a fresh instance of the component (a deep copy that shares
nothing with the original but what lies outside it: the frames it is placed
in). ``add_component`` snapshots a component when it is placed, so reusing
one instance would double-place it — copies sidestep that, and later edits
to the original do not reach them.

Placement follows the original:

* placed with ``add_component`` -> each copy gets the original's pose moved
  by the pattern step (a fixed pose in assembly space);
* placed by a joint -> each copy gets the same joint (type, DOF values,
  limits) on a parent anchor *derived* from the original's parent anchor and
  moved by the pattern step. Derived anchors chain through their base, so
  the copies still follow the parent component when it moves.
* joint relations -> every relation of the assembly that *drives* the
  original's joint (a ``GearRelation`` from the sun to a planet) is copied
  onto each copy's joint, so patterned planets turn with the sun. Relations
  the original's joint drives are not copied (their driven DOF can follow
  only one driver).

No pattern node is serialized: kernels and viewers see the concrete
instances and joints, exactly as if they had been added by hand, and the BOM
and interference checks count every copy.
"""

from __future__ import annotations

import copy
import math
from typing import Any, Optional, Sequence

from .compute_functions import (
    _JOINT_ASSEMBLY_ATTR,
    _JOINT_CHILD_ROOT_ATTR,
    _PLACED_IN_ATTR,
    _RELATION_SPECS,
    _SOURCE_COMPONENT_ATTR,
    _parent_anchor_tf,
    _placement_frame,
    _relation_ends,
    add_joint_method,
    add_relation_method,
    component_frames,
    make_child_anchor,
    unique_derived_anchor_name,
)
from .gen.models import Anchor, Assembly, BoolParameter, Part, RigidJoint
from .gen.runtime import register_method_fn
from .math_utils import (
    axis_angle_to_quaternion,
    compose_tf,
    invert_tf,
    quaternion_rotate_vector,
    tf_relative_to_frame,
    unit_vector,
)

_IDENTITY_Q = [1.0, 0.0, 0.0, 0.0]
# Transient attributes copies must not inherit from the original: where it is
# placed (the copy is placed afresh) and which joint placed it.
_PLACEMENT_ATTRS = (_PLACED_IN_ATTR,)
_JOINT_ATTRS = (_JOINT_ASSEMBLY_ATTR, _JOINT_CHILD_ROOT_ATTR)

Tf = tuple[list[float], list[float]]


def _check_count(count: int, label: str) -> int:
    if isinstance(count, bool) or int(count) != count or count < 1:
        raise ValueError(f"{label}: count must be a positive integer, got {count!r}")
    return int(count)


def _source(component: Any) -> Any:
    """The live Part/Assembly behind ``component`` (which may be its root)."""
    source = getattr(component, _SOURCE_COMPONENT_ATTR, None) or component
    if not isinstance(source, (Part, Assembly)):
        raise TypeError(
            f"Patterns take a Part or an Assembly, got {type(component).__name__}"
        )
    return source


def _fresh_copy(component: Any, extra: Sequence[Any] = ()) -> tuple[Any, list[Any]]:
    """Deep copy of ``component`` (and of ``extra`` objects attached to it,
    e.g. a derived child anchor), sharing only what lies outside it."""
    memo: dict[int, Any] = {}
    # Pin the frames the component hangs from and the assembly holding it.
    for frame in component_frames(component):
        cursor = frame.top_frame
        while cursor is not None:
            memo[id(cursor)] = cursor
            cursor = cursor.top_frame
    placed_in = getattr(component, _PLACED_IN_ATTR, None)
    if placed_in is not None:
        memo[id(placed_in)] = placed_in
    clone, *extra_clones = copy.deepcopy([component, *extra], memo)
    for attr in _PLACEMENT_ATTRS:
        clone.__dict__.pop(attr, None)
    return clone, extra_clones


def _placing_joint(component: Any, assembly: Any) -> Optional[Any]:
    """The joint of ``assembly`` that placed ``component``, if any."""
    for joint in assembly.joints:
        root = getattr(joint, _JOINT_CHILD_ROOT_ATTR, None)
        if root is not None and (
            root is component
            or getattr(root, _SOURCE_COMPONENT_ATTR, None) is component
        ):
            return joint
    return None


def _root_of(component: Any, assembly: Any) -> Any:
    for child in assembly.components:
        if (
            child is component
            or getattr(child, _SOURCE_COMPONENT_ATTR, None) is component
        ):
            return child
    raise ValueError(
        f"'{component.name.value}' is not a component of '{assembly.name.value}'"
    )


def _require_placed_in(component: Any, assembly: Any, label: str) -> None:
    if getattr(component, _PLACED_IN_ATTR, None) is not assembly:
        raise ValueError(
            f"{label}: place '{component.name.value}' in this assembly first "
            "(add_component or add_joint); the pattern copies it from there"
        )


def _copy_joint(joint: Any, parent_anchor: Any, child_anchor: Any) -> Any:
    """Same joint type and values, new anchors (no transient state)."""
    fields = {
        name: getattr(joint, name)
        for name in type(joint).model_fields
        if name not in ("parent_anchor", "child_anchor")
    }
    return type(joint)(parent_anchor=parent_anchor, child_anchor=child_anchor, **fields)


def _driving_relations(assembly: Any, joint: Any) -> list[Any]:
    """Relations of ``assembly`` whose driven end is ``joint``."""
    out = []
    for relation in assembly.relations:
        _, (driven, _) = _relation_ends(relation)
        if driven is joint:
            out.append(relation)
    return out


def _add_joint_copy(assembly: Any, joint: Any, copy_joint: Any) -> None:
    """Add ``copy_joint`` and re-create on it the relations driving ``joint``."""
    add_joint_method(assembly, copy_joint)
    for relation in _driving_relations(assembly, joint):
        driver_field, _, driven_field, _, _ = _RELATION_SPECS[type(relation).__name__]
        fields = {name: getattr(relation, name) for name in type(relation).model_fields}
        if getattr(relation, driven_field) is None:  # ScrewRelation on itself
            fields[driver_field] = copy_joint
        else:
            fields[driven_field] = copy_joint
            if fields[driver_field] is joint:
                fields[driver_field] = copy_joint
        add_relation_method(assembly, type(relation)(**fields))


def _place_copies(
    assembly: Any, component: Any, steps: list[Tf], label: str
) -> list[Any]:
    """Place one copy of ``component`` per rigid ``step`` (assembly space)."""
    component = _source(component)
    _require_placed_in(component, assembly, label)
    instances = [component]
    joint = _placing_joint(component, assembly)
    if joint is None:
        seed_t, seed_q = (
            list(_placement_frame(component, assembly).position),
            list(_placement_frame(component, assembly).quaternion),
        )
        for step in steps:
            clone, _ = _fresh_copy(component)
            assembly.add_component(clone)
            root = _root_of(clone, assembly)
            t, q = compose_tf(*step, seed_t, seed_q)
            root.frame.position = t
            root.frame.quaternion = q
            instances.append(clone)
        return instances

    # Jointed: move the parent anchor by the step, expressed in its own frame
    # (L = Pa⁻¹ · step · Pa), as a derived anchor of the original one.
    anchor_tf = _parent_anchor_tf(joint, assembly)
    for step in steps:
        local_t, local_q = compose_tf(
            *invert_tf(*anchor_tf), *compose_tf(*step, *anchor_tf)
        )
        base = joint.parent_anchor
        parent = make_child_anchor(
            base,
            unique_derived_anchor_name(base, f"{base.name.value}_{label}"),
            local_t,
            local_q,
        )
        clone, (child_anchor,) = _fresh_copy(component, [joint.child_anchor])
        _add_joint_copy(assembly, joint, _copy_joint(joint, parent, child_anchor))
        instances.append(clone)
    return instances


@register_method_fn("assembly_linear_pattern_method")
def assembly_linear_pattern_method(
    inst: Assembly,
    component: Any,
    direction: Sequence[float],
    count: int,
    spacing: float,
) -> list[Any]:
    """``count`` instances of a placed ``component``, ``spacing`` mm apart
    along ``direction`` (assembly space). Returns them, the original first."""
    count = _check_count(count, "linear_pattern")
    step = unit_vector(direction, "direction") * float(spacing)
    steps = [((step * i).tolist(), list(_IDENTITY_Q)) for i in range(1, count)]
    return _place_copies(inst, component, steps, "linear")


@register_method_fn("assembly_polar_pattern_method")
def assembly_polar_pattern_method(
    inst: Assembly,
    component: Any,
    count: int,
    angle_deg: float = 360.0,
    axis: Sequence[float] = (0.0, 0.0, 1.0),
    center: Sequence[float] = (0.0, 0.0, 0.0),
    about: Optional[Any] = None,
) -> list[Any]:
    """``count`` instances of a placed ``component`` rotated about an axis.

    The axis is ``axis`` through ``center`` (assembly space), or the +Z axis
    of the anchor ``about``. ``angle_deg`` is the span: a full turn spaces
    ``angle_deg / count`` (no duplicate at 360°), a partial span
    ``angle_deg / (count - 1)`` so both ends are hit. Returns the instances,
    the original first.
    """
    count = _check_count(count, "polar_pattern")
    if about is not None:
        if not isinstance(about, Anchor):
            raise TypeError(
                f"polar_pattern: about must be an Anchor, got {type(about).__name__}"
            )
        try:
            a_t, a_q = tf_relative_to_frame(about.frame, component_frames(inst))
        except ValueError:
            raise ValueError(
                f"polar_pattern: anchor '{about.name.value}' is not placed in "
                f"'{inst.name.value}'"
            ) from None
        origin, axis_dir = a_t, quaternion_rotate_vector(a_q, [0.0, 0.0, 1.0])
    else:
        origin, axis_dir = [float(c) for c in center], list(axis)
    axis_dir = unit_vector(axis_dir, "axis").tolist()
    span = math.radians(float(angle_deg))
    step = (
        span / count
        if math.isclose(abs(span), 2 * math.pi)
        else span / max(count - 1, 1)
    )
    to_origin = ([-c for c in origin], list(_IDENTITY_Q))
    back = (list(origin), list(_IDENTITY_Q))
    steps = []
    for i in range(1, count):
        spin = ([0.0, 0.0, 0.0], axis_angle_to_quaternion(axis_dir, i * step))
        steps.append(compose_tf(*back, *compose_tf(*spin, *to_origin)))
    return _place_copies(inst, component, steps, "polar")


@register_method_fn("assembly_replicate_method")
def assembly_replicate_method(
    inst: Assembly,
    component: Any,
    onto: Sequence[Any],
    child_anchor: Any = None,
    flip: bool = True,
) -> list[Any]:
    """One instance of ``component`` on every anchor of ``onto``.

    * ``component`` placed by a joint in this assembly: each copy gets the
      same joint (type and values) with an anchor of ``onto`` as parent; an
      anchor that already holds the original is skipped.
    * ``component`` not placed yet: it goes on the first anchor and copies on
      the others, each fastened by a ``RigidJoint`` from the anchor to
      ``child_anchor`` (an Anchor of the component, or its name); ``flip``
      as on joints (True mates the anchors face-to-face).

    Returns the instances, the original first.
    """
    onto = list(onto)
    if not onto:
        raise ValueError(
            "replicate: onto is empty — pass the anchors to place copies on"
        )
    component = _source(component)
    placed_in = getattr(component, _PLACED_IN_ATTR, None)

    if placed_in is None:
        if child_anchor is None:
            raise ValueError(
                f"replicate: '{component.name.value}' is not placed yet — pass "
                "child_anchor= (the anchor of the component that mates onto "
                "each anchor of onto)"
            )
        if isinstance(child_anchor, str):
            child_anchor = component.anchor(child_anchor)
        template = RigidJoint(
            parent_anchor=onto[0],
            child_anchor=child_anchor,
            flip=BoolParameter(value=bool(flip)),
        )
        add_joint_method(inst, template)
        targets = onto[1:]
        joint = template
    else:
        if placed_in is not inst:
            raise ValueError(
                f"replicate: '{component.name.value}' is placed in another "
                f"assembly ('{placed_in.name.value}')"
            )
        if child_anchor is not None:
            raise ValueError(
                "replicate: child_anchor is only for a component that is not "
                "placed yet; a jointed component reuses its joint's anchors"
            )
        joint = _placing_joint(component, inst)
        if joint is None:
            raise ValueError(
                f"replicate: '{component.name.value}' was placed with "
                "add_component, not a joint — replicate needs the joint to "
                "repeat (or pass an unplaced component with child_anchor=)"
            )
        targets = [a for a in onto if a is not joint.parent_anchor]

    instances = [component]
    for anchor in targets:
        clone, (clone_anchor,) = _fresh_copy(component, [joint.child_anchor])
        _add_joint_copy(inst, joint, _copy_joint(joint, anchor, clone_anchor))
        instances.append(clone)
    return instances


__all__ = [
    "assembly_linear_pattern_method",
    "assembly_polar_pattern_method",
    "assembly_replicate_method",
]
