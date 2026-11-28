"""Binding interfaces to parts and joining them: ``add_interface``,
``connect``, ``connect_all``, ``expose``, ``ground`` and ``check``.

Installed as methods on the generated ``Part`` / ``Assembly`` models::

    plate.add_interface(ScrewHole("M5", depth=8), plate.anchor("hole_1"), group="mount")
    asm.ground(plate)
    asm.connect(screw, plate.interface("hole_1"))          # rule ScrewHead <-> ScrewHole
    asm.connect_all(lambda: DIN912Screw("M5", 12), plate.group("mount"))
    asm.check()                                             # [] when clean
"""

from __future__ import annotations

import json
import math
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from ..gen.models import (
    Anchor,
    Assembly,
    BoolParameter,
    Connection,
    FloatParameter,
    Part,
    StringParameter,
)
from ..gen.models import Interface as InterfaceNode
from .rules import (
    JOINTS,
    LIMIT_FIELDS,
    AmbiguousConnect,
    IncompatibleInterfaces,
    LoopMismatch,
    MateError,
    UnsolvedLoop,
    evaluate_rule,
    find_rule,
    normalize_limits,
)
from .types import Interface, clock_step, from_params

__all__ = [
    "InterfaceNode",
    "candidate_pairs",
    "check_assembly",
    "interface_issues",
    "interfaces_of",
    "owner_of",
    "spec_of",
]

_SPEC_ATTR = "_interface_spec"
_OWNER_ATTR = "_interface_owner"
_LINKS_ATTR = "_interface_links"
_LOG_ATTR = "_connect_log"
_GROUNDED_ATTR = "_grounded_components"


# --------------------------------------------------------------------------- #
# Nodes
# --------------------------------------------------------------------------- #


def spec_of(node: Any) -> Interface:
    """The Python interface value of a schema ``Interface`` node."""
    spec = node.__dict__.get(_SPEC_ATTR)
    if spec is None:
        try:
            params = json.loads(node.params.value or "{}")
        except (TypeError, ValueError):
            params = {}
        spec = from_params(node.type.value, params)
        object.__setattr__(node, _SPEC_ATTR, spec)
    return spec


def owner_of(node: Any) -> Any:
    owner = node.__dict__.get(_OWNER_ATTR)
    if owner is None:
        from ..compute_functions import _anchor_owner

        owner = _anchor_owner(node.anchor)
    return owner


def _name_of(node: Any) -> str:
    return node.anchor.name.value


def _label(node: Any) -> str:
    owner = owner_of(node)
    group = node.group.value if node.group is not None else None
    where = f"{owner.name.value}.{_name_of(node)}"
    return f"{where}{f' [{group}]' if group else ''} · {spec_of(node).describe()}"


setattr(InterfaceNode, "spec", property(spec_of))
setattr(InterfaceNode, "owner", property(owner_of))
setattr(InterfaceNode, "iname", property(_name_of))
setattr(InterfaceNode, "label", property(_label))


def _add_interface(
    self: Any,
    interface: Interface,
    anchor: Any = None,
    *,
    group: Optional[str] = None,
    required: bool = False,
    role: Optional[str] = None,
) -> InterfaceNode:
    """Bind ``interface`` to ``anchor`` (an Anchor, or the name of one of this
    component's anchors). The interface is named after its anchor."""
    if not isinstance(interface, Interface):
        raise TypeError(
            f"add_interface: expected a cadbuildr.foundation.interfaces type, got {interface!r}"
        )
    if anchor is None:
        raise TypeError("add_interface: pass the anchor (or its name)")
    if isinstance(anchor, str):
        anchor = self.anchor(anchor)
    if not any(a is anchor for a in self.anchors):
        self.add_anchor(anchor)
    name = anchor.name.value
    if any(_name_of(i) == name for i in self.interfaces):
        raise ValueError(
            f"{type(self).__name__}: anchor '{name}' already carries an interface"
        )
    node = InterfaceNode(
        anchor=anchor,
        type=StringParameter(value=interface.type_name),
        params=StringParameter(value=interface.to_json()),
        role=StringParameter(value=role or interface.role),
        group=StringParameter(value=group) if group else None,
        required=BoolParameter(value=True) if required else None,
    )
    object.__setattr__(node, _SPEC_ATTR, interface)
    object.__setattr__(node, _OWNER_ATTR, self)
    self.interfaces.append(node)
    return node


def _get_interface(self: Any, name: str) -> InterfaceNode:
    for node in self.interfaces:
        if _name_of(node) == name:
            return node
    available = ", ".join(_name_of(i) for i in self.interfaces) or "<none>"
    raise KeyError(
        f"{type(self).__name__} has no interface '{name}' (available: {available})"
    )


def _get_group(self: Any, name: str) -> List[InterfaceNode]:
    members = [
        n for n in self.interfaces if n.group is not None and n.group.value == name
    ]
    if not members:
        groups = sorted({n.group.value for n in self.interfaces if n.group is not None})
        raise KeyError(
            f"{type(self).__name__} has no interface group '{name}' (groups: {groups})"
        )
    return members


for _cls in (Part, Assembly):
    setattr(_cls, "add_interface", _add_interface)
    setattr(_cls, "interface", _get_interface)
    setattr(_cls, "group", _get_group)


def interfaces_of(component: Any) -> List[InterfaceNode]:
    from ..compute_functions import _SOURCE_COMPONENT_ATTR

    source = getattr(component, _SOURCE_COMPONENT_ATTR, None) or component
    return list(getattr(source, "interfaces", None) or [])


# --------------------------------------------------------------------------- #
# Pairing
# --------------------------------------------------------------------------- #


def _is_placed(owner: Any, assembly: Any) -> bool:
    from ..compute_functions import _PLACED_IN_ATTR

    return owner is assembly or getattr(owner, _PLACED_IN_ATTR, None) is not None


_IDENTITY_TF = ([0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0])
_DOF_NAMES = {n for _, names in JOINTS.values() for n in names}


def _mate_tf(mate: Any, swapped: bool) -> Tuple[List[float], List[float]]:
    """``Mate.at`` / ``rotate`` (rule order: on the rule's ``a``) as a
    transform on the *first* interface of the caller's pair. Swapped, the
    same contact seen from ``b``: ``F⁻¹·T⁻¹·F⁻¹`` (``T⁻¹`` without flip)."""
    from ..math_utils import axis_angle_to_quaternion, compose_tf, invert_tf
    from ..placement import _FLIP_Q

    if mate.at is None and not mate.rotate:
        return _IDENTITY_TF
    at = [float(v) for v in (mate.at or (0.0, 0.0, 0.0))]
    if len(at) != 3:
        raise MateError(f"Mate.at must be (x, y, z), got {mate.at!r}")
    tf = (at, axis_angle_to_quaternion([0.0, 0.0, 1.0], float(mate.rotate)))
    if not swapped:
        return tf
    inv = invert_tf(*tf)
    if not mate.flip:
        return inv
    flip_inv = invert_tf([0.0, 0.0, 0.0], _FLIP_Q)
    return compose_tf(*compose_tf(*flip_inv, *inv), *flip_inv)


def _mate_for(
    x: Any,
    y: Any,
    parent: Any = None,
    child: Any = None,
    options: Optional[Dict[str, Any]] = None,
):
    """((rule, mate, tf), failures); ``tf`` moves ``x``'s anchor frame to
    where ``y`` mates (identity unless the rule computes the placement)."""
    found = find_rule(x.type.value, y.type.value)
    if found is None:
        return None, [f"no mate rule for {x.type.value} <-> {y.type.value}"]
    rule, swapped = found
    mate, failures = evaluate_rule(
        rule, swapped, x, y, spec_of(x), spec_of(y), parent, child, options
    )
    return (rule, mate, _mate_tf(mate, swapped)), failures


def candidate_pairs(
    a: Any, b: Any, options: Optional[Dict[str, Any]] = None
) -> Tuple[List[Tuple[Any, Any]], List[str]]:
    """Every compatible (interface of a, interface of b) pair, and why the
    others are not. ``options``: the connect keywords for the rule functions
    (a rule that does not take one is not a candidate)."""
    xs = [a] if isinstance(a, InterfaceNode) else interfaces_of(a)
    ys = [b] if isinstance(b, InterfaceNode) else interfaces_of(b)
    ok, why = [], []
    for x in xs:
        for y in ys:
            res, failures = _mate_for(x, y, options=options)
            if res is not None and not failures:
                ok.append((x, y))
            elif res is not None:
                why.append(f"{_label(x)} <-> {_label(y)}: {'; '.join(failures)}")
    return ok, why


def _make_joint(
    kind: str,
    parent: Any,
    child: Any,
    flip: bool,
    dof: Dict[str, float],
    limits: Any = None,
    parent_anchor: Any = None,
) -> Any:
    from ..gen import models

    cls_name, names = JOINTS[kind]
    unknown = set(dof) - set(names)
    if unknown:
        raise MateError(
            f"a {kind} joint has no DOF {sorted(unknown)} (it takes {list(names)})"
        )
    kwargs: Dict[str, Any] = {k: FloatParameter(value=float(v)) for k, v in dof.items()}
    for name, (lo, hi) in normalize_limits(kind, limits).items():
        kwargs[LIMIT_FIELDS[kind][name]] = models.JointLimits(
            min=FloatParameter(value=lo) if lo is not None else None,
            max=FloatParameter(value=hi) if hi is not None else None,
        )
        value = float(dof.get(name, 0.0))
        if (lo is not None and value < lo - 1e-12) or (
            hi is not None and value > hi + 1e-12
        ):
            raise MateError(
                f"{kind} joint {name} {value:g} is outside its limits "
                f"[{lo}, {hi}]: pass {name}= inside them"
            )
    return getattr(models, cls_name)(
        parent_anchor=parent_anchor if parent_anchor is not None else parent.anchor,
        child_anchor=child.anchor,
        flip=BoolParameter(value=bool(flip)),
        **kwargs,
    )


def _mate_anchor(parent: Any, tf: Tuple[List[float], List[float]], clock: float) -> Any:
    """``parent``'s anchor, or an anchor derived from it by the rule's
    placement ``tf`` and a clocking turn of ``clock`` radians about +Z."""
    from ..compute_functions import make_child_anchor, unique_derived_anchor_name
    from ..math_utils import axis_angle_to_quaternion, compose_tf

    t, q = tf
    if clock:
        t, q = compose_tf(
            t, q, [0.0, 0.0, 0.0], axis_angle_to_quaternion([0.0, 0.0, 1.0], clock)
        )
    if max(abs(v) for v in t) < 1e-12 and abs(abs(q[0]) - 1.0) < 1e-12:
        return parent.anchor
    base = parent.anchor
    name = unique_derived_anchor_name(base, f"{base.name.value}_mate")
    return make_child_anchor(base, name, t, q)


def _log(self: Any) -> List[Dict[str, Any]]:
    log = self.__dict__.get(_LOG_ATTR)
    if log is None:
        log = []
        object.__setattr__(self, _LOG_ATTR, log)
    return log


def _link(node: Any, other: Any) -> None:
    links = node.__dict__.get(_LINKS_ATTR)
    if links is None:
        links = []
        object.__setattr__(node, _LINKS_ATTR, links)
    links.append(other)


def _clock_step(x: Any, y: Any) -> Optional[float]:
    return clock_step(spec_of(x), spec_of(y))


def _connect(
    self: Any,
    a: Any,
    b: Any,
    *,
    name: Optional[str] = None,
    limits: Any = None,
    clock: Optional[int] = None,
    **kwargs: Any,
) -> Any:
    """Join ``a`` and ``b`` (interfaces, or components: then their unique
    compatible pair) with the joint their mate rule gives.

    The side not placed yet becomes the child; when both are placed the
    connection closes a loop and is checked (``LoopClosureError``). DOF
    keywords (``offset``, ``angle`` in radians, ``dx`` / ``dy``) set the
    joint's values; any other keyword is an option of the mate-rule function
    (``connect(tab, slot, clearance=0.2)``). ``limits``: joint limits,
    ``(min, max)`` or ``{"angle": (min, max), "offset": (...)}`` (radians /
    mm), over the rule's own. ``clock=k``: turn the mate by ``k`` steps of the
    interfaces' common clock symmetry (``360 / n`` degrees; a loop closing on
    a clock-symmetric pair snaps to the nearest step by itself). Returns the
    ``Connection``."""
    dof = {k: v for k, v in kwargs.items() if k in _DOF_NAMES}
    options = {k: v for k, v in kwargs.items() if k not in _DOF_NAMES}
    pairs, why = candidate_pairs(a, b, options)
    if not pairs:
        if isinstance(a, InterfaceNode) and isinstance(b, InterfaceNode):
            _, failures = _mate_for(a, b, options=options)
            raise IncompatibleInterfaces(a, b, "; ".join(failures))
        detail = "; ".join(why) or "no interface type pair has a mate rule"
        raise IncompatibleInterfaces(a, b, f"nothing to mate ({detail})")
    if len(pairs) > 1:
        raise AmbiguousConnect(pairs)
    x, y = pairs[0]
    ox, oy = owner_of(x), owner_of(y)
    px, py = _is_placed(ox, self), _is_placed(oy, self)
    if not px and not py:
        raise MateError(
            f"connect: neither {ox.name.value} nor {oy.name.value} is placed; "
            "ground the first part (assembly.ground(part)) and connect from it"
        )
    loop = px and py
    parent, child = (x, y) if (px or loop) else (y, x)
    (rule, mate, tf), failures = _mate_for(
        parent, child, owner_of(parent), owner_of(child), options
    )
    if failures:
        raise IncompatibleInterfaces(parent, child, "; ".join(failures))
    values = {**mate.dof, **dof}
    step = _clock_step(parent, child)
    turn = 0.0
    if clock:
        if step is None:
            raise MateError(
                f"connect: {_label(parent)} and {_label(child)} are axisymmetric; "
                "clock= does nothing (set the joint angle instead)"
            )
        if step >= 2.0 * math.pi - 1e-9:
            raise MateError(
                f"connect: {_label(parent)} and {_label(child)} share no clock "
                "symmetry (give the interfaces clock_symmetry=n)"
            )
        turn = int(clock) * step
    limit_spec = limits if limits is not None else mate.limits

    def build(extra: float = 0.0) -> Any:
        anchor = _mate_anchor(parent, tf, turn + extra)
        return _make_joint(
            mate.joint, parent, child, mate.flip, values, limit_spec, anchor
        )

    joint = build()
    tolerances: Dict[str, float] = {}
    if loop:
        symmetric = _symmetric(parent, child)
        if step is not None and step < 2.0 * math.pi - 1e-9 and not symmetric:
            # Clock-symmetric pair: snap to the nearest symmetry step.
            twist = _residual_twist(joint, self)
            k = round(twist / step)
            if k % round(2.0 * math.pi / step):
                joint = build(k * step)
        pos, ang, along = loop_delta(joint, self, symmetric)
        if _reversible(parent, child) and (pos > _POS_TOL or ang > _ANG_TOL):
            joint.flip = BoolParameter(value=not joint.flip.value)
            other = loop_delta(joint, self, symmetric)
            if other[0] + other[1] < pos + ang:
                pos, ang, along = other
            else:
                joint.flip = BoolParameter(value=not joint.flip.value)
        if pos > _POS_TOL or ang > _ANG_TOL:
            moving = _absorbing_joint(
                self, owner_of(parent), owner_of(child), pos, ang, along
            )
            if moving is not None:
                raise UnsolvedLoop(moving, parent, child, pos, ang)
            raise LoopMismatch(
                parent,
                child,
                pos,
                ang,
                along,
                _hint(self, owner_of(parent), owner_of(child)),
            )
        if symmetric:
            tolerances["angle_tol_deg"] = 180.0  # twist about the axis is don't-care
    connection = Connection(
        name=StringParameter(value=name or f"{_name_of(parent)}-{_name_of(child)}"),
        joint=joint,
        modifiers=list(mate.modifiers),
        interfaces=[parent, child],
    )
    self.add_connection(connection, **tolerances)
    _link(parent, child)
    _link(child, parent)
    _log(self).append(
        {
            "connection": connection,
            "parent": parent,
            "child": child,
            "loop": loop,
            "rule": rule.name,
            "warnings": list(mate.warnings),
        }
    )
    return connection


def _what(x: Any) -> str:
    if isinstance(x, InterfaceNode):
        return _label(x)
    return getattr(getattr(x, "name", None), "value", type(x).__name__)


def _connect_all(
    self: Any,
    parts_or_factory: Union[Callable[[], Any], Sequence[Any]],
    group: Sequence[Any],
    own: Optional[str] = None,
    **dof: float,
) -> List[Any]:
    """One ``connect`` per member of an interface group: a new part from the
    factory (or the next of ``parts``) on each. ``own`` names the part's
    interface (default: its unique compatible one). Returns the parts."""
    members = list(group)
    if callable(parts_or_factory):
        parts = [parts_or_factory() for _ in members]
    else:
        parts = list(parts_or_factory)
        if len(parts) != len(members):
            raise ValueError(
                f"connect_all: {len(parts)} parts for {len(members)} interfaces"
            )
    for part, member in zip(parts, members):
        _connect(self, part.interface(own) if own else part, member, **dof)
    return parts


def _residual_twist(joint: Any, assembly: Any) -> float:
    """Twist (radians, about the parent anchor +Z) by which a loop-closing
    ``joint``'s anchors miss each other."""
    from ..compute_functions import component_frames
    from ..math_utils import compose_tf, invert_tf, tf_relative_to_frame
    from ..placement import _FLIP_Q, _swing_twist_z

    frames = component_frames(assembly)
    p_t, p_q = tf_relative_to_frame(joint.parent_anchor.frame, frames)
    c_t, c_q = tf_relative_to_frame(joint.child_anchor.frame, frames)
    _, j_q = compose_tf(*invert_tf(p_t, p_q), c_t, c_q)
    if joint.flip.value:
        _, j_q = compose_tf([0.0] * 3, j_q, *invert_tf([0.0, 0.0, 0.0], _FLIP_Q))
    twist, _ = _swing_twist_z(j_q)
    return twist


def _expose(
    self: Any,
    node: Any,
    as_: Optional[str] = None,
    *,
    group: Optional[str] = None,
    required: bool = False,
) -> InterfaceNode:
    """Re-export a sub-component's interface as this assembly's own, on an
    assembly anchor ``as_`` at the same pose (an existing anchor of that name
    is reused). Parents then connect the assembly by it."""
    from ..compute_functions import tf_in_component
    from ..helpers import make_anchor

    name = as_ or _name_of(node)
    t, q = tf_in_component(node.anchor.frame, self)
    existing = next((a for a in self.anchors if a.name.value == name), None)
    if existing is not None:
        et, eq = tf_in_component(existing.frame, self)
        dq = min(
            sum((u - v) ** 2 for u, v in zip(eq, q)),
            sum((u + v) ** 2 for u, v in zip(eq, q)),
        )
        if sum((u - v) ** 2 for u, v in zip(et, t)) > 1e-8 or dq > 1e-8:
            raise ValueError(f"expose: anchor '{name}' exists at another pose")
        anchor = existing
    else:
        anchor = self.add_anchor(make_anchor(name, t, q))
    return _add_interface(self, spec_of(node), anchor, group=group, required=required)


_GROUND_DOC = """Fix the first component; connect the rest to it.

* ``ground(part)`` -- a Part / Assembly at the assembly origin;
* ``ground(part, at=(x, y, z), rot_deg=...)`` -- at a pose: ``rot_deg`` in
  degrees (a number about +Z, or ``(rx, ry, rz)`` about the fixed axes), then
  ``at`` in mm;
* ``ground(part, z_axis=(...), x_axis=(...), at=...)`` -- oriented by
  directions instead: the part's +Z goes along ``z_axis`` (and its +X toward
  ``x_axis``), as in ``make_anchor``;
* ``ground(interface_or_anchor, at=..., rot_deg=... | z_axis=...)`` -- the
  anchor is put on that pose (legacy form)."""


def _install_ground() -> None:
    previous = Assembly.ground

    def ground(
        self: Any,
        x: Any,
        *,
        at: Any = None,
        rot_deg: Any = None,
        z_axis: Any = None,
        x_axis: Any = None,
    ) -> Any:
        grounded = self.__dict__.get(_GROUNDED_ATTR)
        if grounded is None:
            grounded = []
            object.__setattr__(self, _GROUNDED_ATTR, grounded)
        if x_axis is not None and z_axis is None:
            raise ValueError("ground: x_axis needs z_axis")
        if z_axis is not None and rot_deg is not None:
            raise TypeError("ground: pass either rot_deg= or z_axis=/x_axis=, not both")
        quaternion = None
        if z_axis is not None:
            from ..math_utils import quaternion_from_directions

            quaternion = list(quaternion_from_directions(z_axis, x_axis))
        if isinstance(x, (Part, Assembly)):
            grounded.append(x)
            _log(self)
            if quaternion is not None:
                tf = {
                    "translation": list(at) if at is not None else [0.0, 0.0, 0.0],
                    "quaternion": quaternion,
                }
                return self.add_component(x, tf=tf)
            return self.add_component(x, at=at, rot_deg=rot_deg)
        anchor = x.anchor if isinstance(x, InterfaceNode) else x
        from ..compute_functions import _anchor_owner

        grounded.append(_anchor_owner(anchor))
        _log(self)
        if quaternion is not None:
            from ..compute_functions import ground_method

            return ground_method(self, anchor, at=at, quaternion=quaternion)
        return previous(self, anchor, at=at, rot_deg=rot_deg)

    ground.__doc__ = _GROUND_DOC
    setattr(Assembly, "ground", ground)


# --------------------------------------------------------------------------- #
# Loops
# --------------------------------------------------------------------------- #

_POS_TOL = 1e-3  # mm
_ANG_TOL = 1e-2  # deg


def _symmetric(x: Any, y: Any) -> bool:
    return bool(
        getattr(spec_of(x), "AXISYMMETRIC", False)
        and getattr(spec_of(y), "AXISYMMETRIC", False)
    )


def _reversible(x: Any, y: Any) -> bool:
    return bool(
        getattr(spec_of(x), "REVERSIBLE", False)
        or getattr(spec_of(y), "REVERSIBLE", False)
    )


def loop_delta(
    joint: Any, assembly: Any, symmetric: bool = False
) -> Tuple[float, float, List[float]]:
    """(mm, deg, gap direction in assembly space) by which ``joint``'s anchors
    miss each other beyond its free DOFs (rotation about the axis is free too
    when both interfaces are axisymmetric)."""
    import math

    from ..compute_functions import component_frames
    from ..math_utils import (
        compose_tf,
        invert_tf,
        quaternion_rotate_vector,
        tf_relative_to_frame,
    )
    from ..placement import _FLIP_Q, _FREE_DOFS, _rotation_angle, _swing_twist_z

    free_t, free_r = _FREE_DOFS[type(joint).__name__]
    frames = component_frames(assembly)
    p_t, p_q = tf_relative_to_frame(joint.parent_anchor.frame, frames)
    c_t, c_q = tf_relative_to_frame(joint.child_anchor.frame, frames)
    j_t, j_q = compose_tf(*invert_tf(p_t, p_q), c_t, c_q)
    if joint.flip.value:
        j_t, j_q = compose_tf(j_t, j_q, *invert_tf([0.0, 0.0, 0.0], _FLIP_Q))
    residual = [0.0 if free_t[i] else j_t[i] for i in range(3)]
    if free_r == "all":
        ang = 0.0
    elif free_r == "z" or symmetric:
        _, ang = _swing_twist_z(j_q)
    else:
        ang = _rotation_angle(j_q)
    pos = math.sqrt(sum(r * r for r in residual))
    along = quaternion_rotate_vector(list(p_q), residual)
    norm = math.sqrt(sum(v * v for v in along)) or 1.0
    return (
        pos,
        math.degrees(ang),
        [v / norm for v in along] if pos > 0 else [0.0, 0.0, 0.0],
    )


def _placing_joints(assembly: Any) -> Dict[int, Any]:
    from ..compute_functions import _anchor_owner

    return {id(_anchor_owner(j.child_anchor)): j for j in assembly.joints}


def _chain(assembly: Any, component: Any, placing: Dict[int, Any]) -> List[Any]:
    from ..compute_functions import _anchor_owner

    out, cursor, seen = [], component, set()
    while id(cursor) in placing and id(cursor) not in seen:
        seen.add(id(cursor))
        joint = placing[id(cursor)]
        out.append(joint)
        cursor = _anchor_owner(joint.parent_anchor)
    return out


def _loop_joints(assembly: Any, a: Any, b: Any) -> List[Any]:
    placing = _placing_joints(assembly)
    ca, cb = _chain(assembly, a, placing), _chain(assembly, b, placing)
    ids_a, ids_b = {id(j) for j in ca}, {id(j) for j in cb}
    return [j for j in ca if id(j) not in ids_b] + [j for j in cb if id(j) not in ids_a]


def _absorbing_joint(
    assembly: Any, a: Any, b: Any, pos: float, ang: float, along: List[float]
) -> Any:
    """The moving joint on the loop whose free DOFs could close the gap
    (then the loop is unsolved, not inconsistent), or None."""
    import numpy as np

    from ..compute_functions import tf_in_component
    from ..math_utils import quaternion_rotate_vector

    moving = [
        j for j in _loop_joints(assembly, a, b) if type(j).__name__ != "RigidJoint"
    ]
    if not moving:
        return None
    if (
        any(
            type(j).__name__
            in (
                "RevoluteJoint",
                "CylindricalJoint",
                "BallJoint",
                "ScrewJoint",
                "PlanarJoint",
            )
            for j in moving
        )
        and ang > _ANG_TOL
    ):
        return next(j for j in moving if type(j).__name__ != "SliderJoint")
    if ang > _ANG_TOL:
        return None  # sliders do not turn anything
    dirs = []
    for j in moving:
        _, q = tf_in_component(j.parent_anchor.frame, assembly)
        kind = type(j).__name__
        if kind in ("RevoluteJoint", "BallJoint"):
            return j  # a rotation could swing the gap closed
        if kind in ("SliderJoint", "CylindricalJoint", "ScrewJoint"):
            dirs.append(quaternion_rotate_vector(list(q), [0.0, 0.0, 1.0]))
        if kind in ("PlanarJoint", "PinSlotJoint"):
            dirs.append(quaternion_rotate_vector(list(q), [1.0, 0.0, 0.0]))
        if kind == "PlanarJoint":
            dirs.append(quaternion_rotate_vector(list(q), [0.0, 1.0, 0.0]))
    gap = np.array(along, dtype=float) * pos
    basis = np.array(dirs, dtype=float).T
    coeffs, *_ = np.linalg.lstsq(basis, gap, rcond=None)
    rest = gap - basis @ coeffs
    if np.linalg.norm(rest) > _POS_TOL:
        return None  # no free DOF on the loop moves that way: inconsistent
    for j, c in zip(moving, coeffs):
        if abs(c) > 1e-9:
            return j
    return moving[0]


def _library_inputs(component: Any) -> Dict[str, Any]:
    from ..compute_functions import _library_ref_of

    ref = _library_ref_of(component)
    if ref is None:
        return {}
    try:
        return json.loads(ref.inputs.value or "{}")
    except Exception:  # pragma: no cover
        return {}


def _hint(assembly: Any, a: Any, b: Any) -> str:
    """The inputs on the loop that disagree (same name, different values)."""
    from ..compute_functions import _anchor_owner

    members: List[Any] = [a, b]
    for joint in _loop_joints(assembly, a, b):
        for anchor in (joint.parent_anchor, joint.child_anchor):
            owner = _anchor_owner(anchor)
            if not any(owner is m for m in members) and owner is not assembly:
                members.append(owner)
    values: Dict[str, Dict[str, Any]] = {}
    labels: List[str] = []
    for m in members:
        label = m.name.value
        if label in labels:  # unnamed parts: tell them apart
            label = f"{label}#{labels.count(label) + 1}"
        labels.append(m.name.value)
        for key, value in _library_inputs(m).items():
            values.setdefault(key, {})[label] = value
    disagree = {
        k: v
        for k, v in values.items()
        if len(v) > 1 and len({json.dumps(x, sort_keys=True) for x in v.values()}) > 1
    }
    if disagree:
        parts = "; ".join(
            f"{k}: " + ", ".join(f"{n}={val!r}" for n, val in v.items())
            for k, v in sorted(disagree.items())
        )
        return f"Inputs that disagree around the loop: {parts}."
    shared = sorted(k for k, v in values.items() if len(v) > 1)
    names = ", ".join(m.name.value for m in members)
    return (
        f"Check the sizes around the loop ({names})"
        + (f"; shared inputs: {', '.join(shared)}" if shared else "")
        + "."
    )


# --------------------------------------------------------------------------- #
# check()
# --------------------------------------------------------------------------- #


def _issue(
    severity: str,
    code: str,
    message: str,
    components: Iterable[str] = (),
    interfaces: Iterable[str] = (),
    delta: Optional[Dict[str, Any]] = None,
    fix: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "severity": severity,
        "code": code,
        "interfaces": list(interfaces),
        "components": list(components),
        "delta": delta,
        "message": message,
        "fix": fix,
    }


def check_assembly(
    self: Any,
    interference: bool = False,
    tol: float = _POS_TOL,
    recursive: bool = True,
) -> List[Dict[str, Any]]:
    """Constraint status of an assembly built with interfaces, as
    ``[{severity, code, interfaces, components, delta, message, fix}]``
    (see :func:`interface_issues` for the codes), followed -- with
    ``recursive=True`` (default) -- by the checks of everything under it:
    sub-assemblies' interface checks and every part / assembly
    ``__checks__`` hook or attached report
    (:func:`cadbuildr.foundation.checks.collect_checks`). Issues of nested
    components name them by path (``sub/part``)."""
    issues = interface_issues(self, interference=interference, tol=tol)
    if recursive:
        from ..checks import _collect

        issues += _collect(self, None, False, False)
    return issues


def interface_issues(
    self: Any, interference: bool = False, tol: float = _POS_TOL
) -> List[Dict[str, Any]]:
    """The interface checks of ``self`` alone (no recursion):

    * ``coordinates`` (warning) -- placed by ``add_component`` with no connect
      (every component but the grounded one should be connected);
    * ``unconnected`` (warning) -- a ``required`` interface no connect uses;
    * ``loop`` (error) -- a connection whose interfaces no longer meet beyond
      its free DOFs (a loop broken after a DOF or size change), ``delta`` =
      ``{mm, deg, along}``;
    * ``moves`` (info) -- a free DOF that matters (slider offset, revolute
      angle on a non-axisymmetric pair, planar dx / dy), with its value;
    * ``interference`` (warning, ``interference=True``) -- overlapping parts.
    """
    from ..compute_functions import _JOINT_CHILD_ROOT_ATTR, _SOURCE_COMPONENT_ATTR

    issues: List[Dict[str, Any]] = []
    grounded = self.__dict__.get(_GROUNDED_ATTR) or []
    jointed = {id(getattr(j, _JOINT_CHILD_ROOT_ATTR, None)) for j in self.joints}
    for root in self.components:
        source = getattr(root, _SOURCE_COMPONENT_ATTR, None) or root
        name = root.name.value
        if id(root) not in jointed and not any(g is source for g in grounded):
            issues.append(
                _issue(
                    "warning",
                    "coordinates",
                    f"{name} is placed by coordinates (add_component), not by a connect",
                    [name],
                    fix=f"connect {name} by one of its interfaces instead of add_component",
                )
            )
        for node in interfaces_of(source):
            if (
                node.required is not None
                and node.required.value
                and not node.__dict__.get(_LINKS_ATTR)
            ):
                issues.append(
                    _issue(
                        "warning",
                        "unconnected",
                        f"required interface {_label(node)} is not connected",
                        [name],
                        [_label(node)],
                        fix=f"connect {_label(node)}",
                    )
                )
    for entry in self.__dict__.get(_LOG_ATTR) or []:
        joint = entry["connection"].joint
        parent, child = entry["parent"], entry["child"]
        names = [owner_of(parent).name.value, owner_of(child).name.value]
        labels = [_label(parent), _label(child)]
        symmetric = _symmetric(parent, child)
        try:
            pos, ang, along = loop_delta(joint, self, symmetric)
        except Exception as exc:  # pragma: no cover - unresolvable anchors
            issues.append(
                _issue(
                    "error",
                    "loop",
                    f"{entry['connection'].name.value}: {exc}",
                    names,
                    labels,
                )
            )
            continue
        if pos > tol or ang > _ANG_TOL:
            issues.append(
                _issue(
                    "error",
                    "loop",
                    f"{labels[0]} and {labels[1]} are off by {pos:.3f} mm / {ang:.3f} deg",
                    names,
                    labels,
                    {"mm": pos, "deg": ang, "along": along},
                    _hint(self, owner_of(parent), owner_of(child)),
                )
            )
        for w in entry.get("warnings") or []:
            issues.append(
                _issue(
                    w.get("severity") or "warning",
                    w["code"],
                    f"{entry['connection'].name.value}: {w['message']}",
                    names,
                    labels,
                    w.get("delta"),
                    w.get("fix"),
                )
            )
        if not entry["loop"]:
            kind = type(joint).__name__
            dofs = {
                k: getattr(joint, k).value
                for k in ("offset", "dx", "dy", "angle")
                if hasattr(joint, k) and getattr(joint, k) is not None
            }
            if symmetric and kind in ("RevoluteJoint", "CylindricalJoint"):
                dofs.pop("angle", None)  # turning an axisymmetric pair changes nothing
            if dofs:
                text = ", ".join(f"{k} {v:g}" for k, v in dofs.items())
                issues.append(
                    _issue(
                        "info",
                        "moves",
                        f"{names[1]} moves ({text})",
                        [names[1]],
                        labels,
                        {"dof": dofs},
                    )
                )
    if interference:
        for hit in self.check_interference(include_unknown=False):
            if hit.status == "overlap":
                issues.append(_issue("warning", "interference", str(hit)))
    return issues


setattr(Assembly, "connect", _connect)
setattr(Assembly, "connect_all", _connect_all)
setattr(Assembly, "expose", _expose)
setattr(Assembly, "check", check_assembly)
_install_ground()


def uses_interfaces(obj: Any) -> bool:
    """True for an assembly built with ground / connect (check() applies)."""
    from ..compute_functions import _SOURCE_COMPONENT_ATTR

    source = getattr(obj, _SOURCE_COMPONENT_ATTR, None) or obj
    return isinstance(source, Assembly) and source.__dict__.get(_LOG_ATTR) is not None
