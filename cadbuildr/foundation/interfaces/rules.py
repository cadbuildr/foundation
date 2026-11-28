"""Mate rules: one table mapping a pair of interface types to a joint.

::

    @mate_rule(ScrewHead, ScrewHole, joint="rigid", equal=[("size", "size")])
    def screw_in_hole(head, hole, ctx):
        ctx.require(ctx.length_ok(head, hole), "screw too short for the grip")
        return Mate(modifiers=[] if hole.drilled is not False else [ctx.clearance()])

A rule is order-insensitive (``connect(hole, head)`` finds it too) and is
declarative where it can be (type pair, joint, flip, parameter-equality
keys, default DOF values: :func:`export_rules`); the optional function adds
checks and modifiers, and may override the joint / flip / DOF values /
limits, or compute the placement itself (``Mate(at=..., rotate=...)``: a
gear centre distance from the modules and tooth counts, a rack phase).
Keywords of ``connect`` that are not DOF values reach the function as
keyword arguments (and ``ctx.options``)::

    @mate_rule(SheetTab, SheetSlot)
    def tab_in_slot(tab, slot, ctx, clearance=0.1): ...
    asm.connect(tab, slot, clearance=0.2)

Libraries register their own rules the same way.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Type, Union

from .types import (
    BearingFace,
    BearingPocket,
    BearingSeat,
    Bore,
    Interface,
    NemaBody,
    NemaFace,
    NutSeat,
    PivotHole,
    PivotPin,
    PlaneFace,
    RodAxis,
    RodEnd,
    RodHole,
    ScrewHead,
    ScrewHole,
    ScrewTip,
    Shaft,
    ShaftEnd,
    SlideCarriage,
    SlideRail,
    StructuralEnd,
    TSlot,
    TSlotNutSeat,
    same_value,
)

__all__ = [
    "JOINTS",
    "Mate",
    "MateContext",
    "AmbiguousConnect",
    "IncompatibleInterfaces",
    "LoopMismatch",
    "MateError",
    "UnsolvedLoop",
    "Rule",
    "LIMIT_FIELDS",
    "export_rules",
    "find_rule",
    "mate_rule",
    "normalize_limits",
    "rules",
    "thread_engagement",
]

# joint kind -> (Joint class name, DOF names in the order the joint takes them)
JOINTS: Dict[str, Tuple[str, Tuple[str, ...]]] = {
    "rigid": ("RigidJoint", ()),
    "slider": ("SliderJoint", ("offset",)),
    "revolute": ("RevoluteJoint", ("angle",)),
    "cylindrical": ("CylindricalJoint", ("angle", "offset")),
    "planar": ("PlanarJoint", ("dx", "dy", "angle")),
    "screw": ("ScrewJoint", ("angle",)),
}


class MateError(ValueError):
    """Base of the errors ``connect`` raises."""


# joint kind -> {DOF: JointLimits field of the joint}
LIMIT_FIELDS: Dict[str, Dict[str, str]] = {
    "slider": {"offset": "limits"},
    "revolute": {"angle": "limits"},
    "screw": {"angle": "limits"},
    "cylindrical": {"angle": "angle_limits", "offset": "offset_limits"},
}

# What connect / Mate / mate_rule take as ``limits``: ``(min, max)`` for a
# joint with one limited DOF, or ``{"angle": (min, max), "offset": ...}``;
# either bound may be None (open). Radians for angles, mm for offsets.
LimitsSpec = Union[Sequence[Optional[float]], Dict[str, Sequence[Optional[float]]]]


def normalize_limits(
    joint: str, limits: Optional[LimitsSpec]
) -> Dict[str, Tuple[Optional[float], Optional[float]]]:
    """``limits`` as ``{dof: (min, max)}`` for a ``joint`` kind; raises
    :class:`MateError` when the joint cannot limit that DOF."""
    if limits is None:
        return {}
    fields = LIMIT_FIELDS.get(joint, {})
    if not isinstance(limits, dict):
        if len(fields) != 1:
            raise MateError(
                f"limits=(min, max) needs a joint with one limited DOF; a {joint} "
                f"joint limits {list(fields) or 'nothing'} (pass {{dof: (min, max)}})"
            )
        limits = {next(iter(fields)): limits}
    out: Dict[str, Tuple[Optional[float], Optional[float]]] = {}
    for dof, bounds in limits.items():
        if dof not in fields:
            raise MateError(
                f"a {joint} joint cannot limit {dof!r} "
                f"(limited DOFs: {list(fields) or 'none'})"
            )
        lo, hi = bounds
        lo = None if lo is None else float(lo)
        hi = None if hi is None else float(hi)
        if lo is not None and hi is not None and lo > hi:
            raise MateError(f"limits for {dof}: min {lo} > max {hi}")
        out[dof] = (lo, hi)
    return out


class IncompatibleInterfaces(MateError):
    """No rule pairs the two interface types, or a rule check failed."""

    def __init__(self, a: Any, b: Any, reason: str) -> None:
        self.a, self.b, self.reason = a, b, reason
        super().__init__(f"incompatible interfaces {_lbl(a)} and {_lbl(b)}: {reason}")


class AmbiguousConnect(MateError):
    """A component-level connect matches several interface pairs."""

    def __init__(self, candidates: Sequence[Tuple[Any, Any]]) -> None:
        self.candidates = list(candidates)
        listed = "\n  ".join(f"{_lbl(x)}  <->  {_lbl(y)}" for x, y in self.candidates)
        super().__init__(
            f"connect: {len(self.candidates)} ways to mate; pass the interfaces:\n  {listed}"
        )


class LoopMismatch(MateError):
    """A loop-closing connect whose interfaces do not meet (over-constrained
    and inconsistent): ``delta_mm`` / ``delta_deg`` off, ``along`` the gap
    direction (assembly frame), ``hint`` naming the inputs that disagree."""

    def __init__(
        self,
        a: Any,
        b: Any,
        delta_mm: float,
        delta_deg: float,
        along: Sequence[float],
        hint: str,
    ) -> None:
        self.a, self.b = a, b
        self.delta_mm, self.delta_deg = float(delta_mm), float(delta_deg)
        self.along, self.hint = [float(v) for v in along], hint
        super().__init__(
            f"{_lbl(a)} and {_lbl(b)} close a loop but are off by {self.delta_mm:.3f} mm"
            f" / {self.delta_deg:.3f} deg (along {[round(v, 3) for v in self.along]}). {hint}"
        )


class UnsolvedLoop(MateError):
    """A loop that does not close through a moving joint (v1 does not solve
    the free DOF on the loop: set that joint's value, or connect differently)."""

    def __init__(
        self, joint: Any, a: Any, b: Any, delta_mm: float, delta_deg: float
    ) -> None:
        self.joint, self.a, self.b = joint, a, b
        self.delta_mm, self.delta_deg = float(delta_mm), float(delta_deg)
        super().__init__(
            f"{_lbl(a)} and {_lbl(b)} close a loop through the moving "
            f"{type(joint).__name__} '{joint.child_anchor.name.value}' and are off by "
            f"{self.delta_mm:.3f} mm / {self.delta_deg:.3f} deg: set that joint's value "
            "so the loop closes (loops through moving joints are not solved yet)"
        )


def _lbl(node: Any) -> str:
    return getattr(node, "label", None) or repr(node)


@dataclass
class Mate:
    """What a rule resolves a pair to. ``None`` fields keep the rule's
    declarative value.

    ``at`` (mm) / ``rotate`` (radians about +Z) place the mate away from the
    anchors: the rule's ``a`` interface frame moved by ``at`` and then turned
    by ``rotate`` is where ``b`` mates (a gear centre distance, a tooth
    phase). ``limits``: joint limits as :func:`normalize_limits` takes them."""

    joint: Optional[str] = None
    flip: Optional[bool] = None
    dof: Dict[str, float] = field(default_factory=dict)
    modifiers: List[Any] = field(default_factory=list)
    at: Optional[Sequence[float]] = None
    rotate: float = 0.0
    limits: Optional[LimitsSpec] = None
    # Non-fatal findings (``ctx.warn``): they do not block the connect and
    # show up in ``assembly.check()`` / the DAG ``checks``.
    warnings: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Rule:
    a: Type[Interface]
    b: Type[Interface]
    joint: str = "rigid"
    flip: bool = True
    equal: Tuple[Tuple[str, str], ...] = ()
    dof: Dict[str, float] = field(default_factory=dict)
    fn: Optional[Callable[..., Optional[Mate]]] = None
    name: str = ""
    doc: str = ""
    limits: Optional[LimitsSpec] = None
    options: Tuple[str, ...] = ()

    def _extra_params(self) -> List[inspect.Parameter]:
        if self.fn is None:
            return []
        return list(inspect.signature(self.fn).parameters.values())[3:]

    def accepts(self, option: str) -> bool:
        """True when ``connect(..., option=...)`` is meant for this rule: it
        is declared in ``options`` or the function takes it as a keyword."""
        if option in self.options:
            return True
        return any(
            p.kind is inspect.Parameter.VAR_KEYWORD
            or (p.name == option and p.kind is not inspect.Parameter.VAR_POSITIONAL)
            for p in self._extra_params()
        )

    def to_json(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "name": self.name,
            "a": self.a.__name__,
            "b": self.b.__name__,
            "joint": self.joint,
            "jointType": JOINTS[self.joint][0],
            "flip": self.flip,
            "equal": [list(p) for p in self.equal],
            "dof": dict(self.dof),
            "dofNames": list(JOINTS[self.joint][1]),
            "checks": bool(self.fn),
            "doc": self.doc,
        }
        limits = normalize_limits(self.joint, self.limits)
        if limits:  # keys only when set, so older tables read the same
            out["limits"] = {k: list(v) for k, v in limits.items()}
        options = sorted(
            {*self.options}
            | {
                p.name
                for p in self._extra_params()
                if p.kind
                in (
                    inspect.Parameter.KEYWORD_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                )
            }
        )
        if options:
            out["options"] = options
        return out


_RULES: Dict[Tuple[str, str], Rule] = {}


def mate_rule(
    a: Type[Interface],
    b: Type[Interface],
    *,
    joint: str = "rigid",
    flip: bool = True,
    equal: Sequence[Any] = (),
    dof: Optional[Dict[str, float]] = None,
    name: Optional[str] = None,
    limits: Optional[LimitsSpec] = None,
    options: Sequence[str] = (),
) -> Callable[[Callable], Callable]:
    """Register a rule for the (``a``, ``b``) interface type pair.

    ``equal``: parameter keys that must match, ``"size"`` or
    ``("size_on_a", "size_on_b")``. ``dof``: default joint values.
    ``limits``: default joint limits (``(min, max)`` or ``{dof: (min, max)}``,
    radians / mm). ``options``: ``connect`` keywords the function reads from
    ``ctx.options`` (keyword parameters of the function count already). Used
    bare as ``mate_rule(A, B, ...)(None)`` it registers a declarative rule.
    """
    if joint not in JOINTS:
        raise ValueError(f"mate_rule: unknown joint {joint!r} (one of {list(JOINTS)})")
    pairs = tuple((k, k) if isinstance(k, str) else (k[0], k[1]) for k in equal)
    unknown = set(dof or {}) - set(JOINTS[joint][1])
    if unknown:
        raise ValueError(f"mate_rule: {joint} joint has no DOF {sorted(unknown)}")
    normalize_limits(joint, limits)  # validate up front

    def register(fn: Optional[Callable]) -> Optional[Callable]:
        rule = Rule(
            a=a,
            b=b,
            joint=joint,
            flip=flip,
            equal=pairs,
            dof=dict(dof or {}),
            fn=fn,
            name=name
            or (getattr(fn, "__name__", None) or f"{a.__name__}_{b.__name__}"),
            doc=((getattr(fn, "__doc__", None) or "").strip().splitlines() or [""])[0],
            limits=limits,
            options=tuple(options),
        )
        _RULES[(a.__name__, b.__name__)] = rule
        return fn

    return register


def rules() -> List[Rule]:
    return list(_RULES.values())


def find_rule(type_a: str, type_b: str) -> Optional[Tuple[Rule, bool]]:
    """(rule, swapped): ``swapped`` when the rule is declared (b, a)."""
    if (type_a, type_b) in _RULES:
        return _RULES[(type_a, type_b)], False
    if (type_b, type_a) in _RULES:
        return _RULES[(type_b, type_a)], True
    return None


def export_rules() -> Dict[str, Any]:
    """The declarative rule table (manifest / CLI ``rules``)."""
    from .types import interface_types

    types = {}
    for tname, cls in sorted(interface_types().items()):
        types[tname] = {
            "params": list(cls.PARAMS),
            "role": cls.ROLE,
            "axisymmetric": bool(cls.AXISYMMETRIC),
            "reversible": bool(cls.REVERSIBLE),
            "doc": ((cls.__doc__ or "").strip().splitlines() or [""])[0],
        }
        if int(cls.CLOCK_SYMMETRY) > 1:  # only when set: older tables read the same
            types[tname]["clockSymmetry"] = int(cls.CLOCK_SYMMETRY)
    return {
        "format": "cadbuildr.mate-rules/1",
        "types": types,
        "joints": {k: {"type": v[0], "dof": list(v[1])} for k, v in JOINTS.items()},
        "rules": [r.to_json() for r in rules()],
    }


class MateContext:
    """What a rule function sees: both interface nodes, both specs (in rule
    order), the parent / child components (None while only previewing) and
    ``require`` for checks. ``options``: the non-DOF keywords of ``connect``."""

    def __init__(
        self,
        a_node: Any,
        b_node: Any,
        a: Interface,
        b: Interface,
        parent: Any = None,
        child: Any = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.a_node, self.b_node, self.a, self.b = a_node, b_node, a, b
        self.parent, self.child = parent, child
        self.options: Dict[str, Any] = dict(options or {})
        self.failures: List[str] = []

        self.warnings: List[Dict[str, Any]] = []

    def require(self, condition: Any, message: str) -> bool:
        if not condition:
            self.failures.append(message)
        return bool(condition)

    def warn(
        self,
        code: str,
        message: str,
        severity: str = "warning",
        delta: Optional[Dict[str, Any]] = None,
        fix: Optional[str] = None,
    ) -> None:
        """A non-fatal finding: the connect goes ahead and the issue shows
        up in ``assembly.check()`` (``code`` e.g. ``thread_engagement``)."""
        self.warnings.append(
            {
                "severity": severity,
                "code": code,
                "message": message,
                "delta": delta,
                "fix": fix,
            }
        )

    def owner(self, node: Any) -> Any:
        return getattr(node, "_owner", None) if node is not None else None

    def clearance(
        self, node: Any = None, depth: Optional[float] = None, fit: str = "NORMAL"
    ) -> Any:
        """A ``PartModifier`` drilling the clearance hole of a ``ScrewHole``
        node (default: whichever side is the ScrewHole) into its part."""
        node = node or (self.a_node if isinstance(self.a, ScrewHole) else self.b_node)
        spec = self.a if node is self.a_node else self.b
        return clearance_modifier(
            node.anchor, spec.size, depth or spec.depth or 10.0, fit
        )


def clearance_modifier(
    anchor: Any, size: Any, depth: float, fit: str = "NORMAL"
) -> Any:
    from ..gen.models import Circle, Extrusion, PartModifier, Sketch
    from ..helpers import anchor_plane
    from ..holes import clearance_diameter

    d = float(str(size).lstrip("Mm"))
    sketch = Sketch(anchor_plane(anchor))
    return PartModifier(
        anchor=anchor,
        operations=[
            Extrusion(
                Circle(sketch.origin, clearance_diameter(d, fit) / 2.0),
                0.0,
                -float(depth),
                cut=True,
            )
        ],
    )


def evaluate_rule(
    rule: Rule,
    swapped: bool,
    x_node: Any,
    y_node: Any,
    x: Interface,
    y: Interface,
    parent: Any = None,
    child: Any = None,
    options: Optional[Dict[str, Any]] = None,
) -> Tuple[Mate, List[str]]:
    """Run ``rule`` on (x, y) given in caller order; returns the mate (its
    ``at`` / ``rotate`` in rule order) and the list of failed checks."""
    a_node, b_node, a, b = (y_node, x_node, y, x) if swapped else (x_node, y_node, x, y)
    options = dict(options or {})
    ctx = MateContext(a_node, b_node, a, b, parent, child, options)
    for key in options:
        ctx.require(rule.accepts(key), f"rule {rule.name} takes no option {key!r}")
    for ka, kb in rule.equal:
        ctx.require(
            same_value(a.params.get(ka), b.params.get(kb)),
            f"{a.type_name}.{ka}={a.params.get(ka)!r} != {b.type_name}.{kb}={b.params.get(kb)!r}",
        )
    mate = Mate()
    if rule.fn is not None and not ctx.failures:
        extra = rule._extra_params()
        if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in extra):
            kwargs = options
        else:
            names = {p.name for p in extra}
            kwargs = {k: v for k, v in options.items() if k in names}
        mate = rule.fn(a, b, ctx, **kwargs) or Mate()
    resolved = Mate(
        joint=mate.joint or rule.joint,
        flip=rule.flip if mate.flip is None else mate.flip,
        dof={**rule.dof, **mate.dof},
        modifiers=list(mate.modifiers),
        at=mate.at,
        rotate=float(mate.rotate or 0.0),
        limits=mate.limits if mate.limits is not None else rule.limits,
        warnings=[*mate.warnings, *ctx.warnings],
    )
    return resolved, ctx.failures


# --------------------------------------------------------------------------- #
# Core rules
# --------------------------------------------------------------------------- #


# Minimum thread engagement, as a multiple of the nominal diameter: steel
# nut / steel part ~1 d; aluminium, cast iron, plastics need more.
MIN_THREAD_ENGAGEMENT = 1.0


def _nominal_d(size: Any) -> Optional[float]:
    try:
        return float(str(size).lstrip("Mm").split("x")[0])
    except (TypeError, ValueError):
        return None


def thread_engagement(
    length: Any,
    size: Any,
    thread_depth: Any,
    grip: float = 0.0,
    min_ratio: float = MIN_THREAD_ENGAGEMENT,
) -> Dict[str, Any]:
    """Engagement of a screw (``length`` under head, ``size`` "M5") in a
    tapped hole ``thread_depth`` deep, after ``grip`` mm of clamped
    material: ``{engagement, required, ok, bottoms_out}`` (mm)."""
    d = _nominal_d(size)
    tip = float(length) - float(grip)
    depth = float(thread_depth)
    engagement = max(0.0, min(tip, depth))
    required = (d or 0.0) * float(min_ratio)
    return {
        "engagement": engagement,
        "required": required,
        "ok": engagement + 1e-9 >= required,
        "bottoms_out": tip > depth + 1e-9,
    }


@mate_rule(ScrewHead, ScrewHole, equal=["size"])
def screw_in_hole(head, hole, ctx):
    """A screw head seats on a hole face; the shank goes into the hole."""
    if head.length is not None and hole.depth is not None and not hole.thread:
        ctx.require(
            float(head.length) >= float(hole.depth), "screw too short for the grip"
        )
    if head.length is not None and hole.depth is not None and hole.thread:
        # Tapped hole under the head: the tip engages over min(length, depth).
        e = thread_engagement(head.length, hole.size, hole.depth)
        delta = {k: e[k] for k in ("engagement", "required")}
        if not e["ok"]:
            ctx.warn(
                "thread_engagement",
                f"{hole.size} engages {e['engagement']:.1f} mm of thread, needs "
                f">= {e['required']:.1f} mm ({MIN_THREAD_ENGAGEMENT:g} x d)",
                delta=delta,
                fix="use a longer screw or a deeper tapped hole",
            )
        if e["bottoms_out"]:
            # info: the head may sit on a plate tapped only part-way, or the
            # hole may run on (blind depth unknown to the rule).
            ctx.warn(
                "thread_bottoms_out",
                f"{hole.size} x {float(head.length):g} screw is longer than the "
                f"{float(hole.depth):g} mm tapped depth: it bottoms out",
                delta=delta,
                fix="use a shorter screw or tap deeper",
                severity="info",
            )
    if hole.drilled is False:
        return Mate(
            modifiers=[ctx.clearance(ctx.b_node, depth=(head.length or hole.depth))]
        )
    return None


@mate_rule(NutSeat, ScrewHole, equal=["size"])
def nut_on_hole(nut, hole, ctx):
    """A nut / washer / spacer face on a hole face (the exit side of a bolt)."""
    return None


@mate_rule(NutSeat, ScrewTip, joint="slider", equal=["size"])
def nut_on_screw(nut, tip, ctx):
    """A nut threaded on a screw: slides along the shank from the tip (offset < 0 runs it on)."""
    return None


@mate_rule(Shaft, Bore, joint="cylindrical", flip=False, equal=[("d", "d")])
def shaft_in_bore(shaft, bore, ctx):
    """A bore on a shaft: coaxial, slides (offset) and turns (angle)."""
    return None


@mate_rule(ShaftEnd, Bore, equal=[("d", "d")])
def shaft_end_in_bore(end, bore, ctx):
    """A shaft tip against a bore stop (couplings, blind bores)."""
    return None


@mate_rule(BearingFace, BearingSeat, equal=["model"])
def bearing_in_seat(face, seat, ctx):
    """A rolling bearing face on its seat shoulder."""
    return None


@mate_rule(BearingFace, RodAxis, joint="slider")
def bearing_on_rod(face, rod, ctx):
    """A linear bearing slides on a smooth rod (offset along the rod)."""
    ctx.require(same_value(face.d, rod.d), f"bearing bore {face.d} != rod {rod.d}")
    return None


@mate_rule(BearingFace, BearingPocket)
def bearing_in_pocket(face, pocket, ctx):
    """A linear bearing in a carriage pocket sized for its rod."""
    ctx.require(
        same_value(face.d, pocket.rod),
        f"bearing bore {face.d} != pocket rod {pocket.rod}",
    )
    ctx.require(
        same_value(face.model, pocket.model),
        f"bearing {face.model} != pocket {pocket.model}",
    )
    return None


@mate_rule(RodEnd, RodHole, equal=["d"])
def rod_in_hole(end, hole, ctx):
    """A rod end fixed in a rod hole."""
    return None


@mate_rule(NemaBody, NemaFace, equal=["frame"])
def motor_on_face(body, face, ctx):
    """A NEMA motor front face on a motor mount face."""
    return None


@mate_rule(TSlotNutSeat, TSlot, joint="planar", flip=False, equal=["slot"])
def tnut_in_slot(nut, slot, ctx):
    """A T-slot nut in a profile slot: slides along it (dx)."""
    return None


@mate_rule(TSlot, PlaneFace, joint="planar")
def profile_on_face(slot, face, ctx):
    """A profile face (at a slot) flat on a face: dx / dy / angle in the face plane."""
    return None


@mate_rule(TSlot, TSlot, joint="planar")
def profile_on_profile(a, b, ctx):
    """A profile flat on another profile (crossed frame members)."""
    return None


@mate_rule(PlaneFace, PlaneFace)
def face_to_face(a, b, ctx):
    """Two flat faces against each other."""
    return None


@mate_rule(PivotHole, PivotPin, joint="revolute", equal=["d"])
def link_on_pivot(hole, pin, ctx):
    """A link's pivot bore on a pin: turns about the pin (angle)."""
    return None


@mate_rule(SlideCarriage, SlideRail, joint="slider", flip=False, equal=["profile"])
def carriage_on_rail(carriage, rail, ctx):
    """A carriage on its guide rail: slides along it (offset)."""
    return None


_FIXITY = ("fixed", "pinned")


def _fixity_ok(end: Any, ctx: MateContext) -> None:
    ctx.require(
        end.fixity is None or end.fixity in _FIXITY,
        f"StructuralEnd fixity {end.fixity!r} is not one of {list(_FIXITY)}",
    )


@mate_rule(StructuralEnd, StructuralEnd)
def member_to_member(a, b, ctx):
    """Two member ends joined end to end (a splice); fixity is analysis data."""
    _fixity_ok(a, ctx)
    _fixity_ok(b, ctx)
    return None


@mate_rule(StructuralEnd, PlaneFace)
def member_on_face(end, face, ctx):
    """A member end on a flat face (base plate, column flange, wall)."""
    _fixity_ok(end, ctx)
    return None
