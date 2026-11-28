"""Interface types: what a mating site of a component *is*.

An interface type is a small value object: a type name (the class name) and
JSON parameters computed from the part's inputs (``ScrewHole(size="M5",
depth=6)``). Bound to an anchor of a part (``part.add_interface``) it becomes
a schema ``Interface`` node in the DAG. New types need no schema change:
subclass :class:`Interface` (the class name is the type name) and register
mate rules for it (:func:`~cadbuildr.foundation.interfaces.rules.mate_rule`).
"""

from __future__ import annotations

import json
import math
from typing import Any, ClassVar, Dict, Optional, Type

__all__ = [
    "Bore",
    "BearingFace",
    "BearingPocket",
    "BearingSeat",
    "Interface",
    "NemaBody",
    "NemaFace",
    "NutSeat",
    "PivotHole",
    "PivotPin",
    "PlaneFace",
    "RodAxis",
    "RodEnd",
    "RodHole",
    "ScrewHead",
    "ScrewHole",
    "ScrewTip",
    "Shaft",
    "ShaftEnd",
    "SlideCarriage",
    "SlideRail",
    "StructuralEnd",
    "TSlot",
    "TSlotNutSeat",
    "clock_step",
    "interface_type",
    "interface_types",
    "same_value",
]

_TYPES: Dict[str, Type["Interface"]] = {}


def _jsonable(value: Any) -> Any:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        f = float(value)
        return int(f) if f.is_integer() else f
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if hasattr(value, "tolist") and not isinstance(value, (str, bytes)):
        return _jsonable(value.tolist())  # numpy arrays
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    try:  # numpy scalars, enums...
        return _jsonable(value.item())
    except Exception:
        return str(getattr(value, "name", value))


def same_value(a: Any, b: Any, tol: float = 1e-6) -> bool:
    """Parameter equality across the forms inputs take (``"8"`` == ``8`` ==
    ``8.0``); ``None`` on either side matches anything (unsized).

    List-valued parameters: two lists match element by element (same
    length); a scalar matches a list that contains it (``"M4"`` fits
    ``sizes=["M3", "M4"]``)."""
    if a is None or b is None:
        return True
    a_list, b_list = isinstance(a, (list, tuple)), isinstance(b, (list, tuple))
    if a_list and b_list:
        return len(a) == len(b) and all(same_value(x, y, tol) for x, y in zip(a, b))
    if a_list or b_list:
        items, scalar = (a, b) if a_list else (b, a)
        return any(same_value(x, scalar, tol) for x in items)
    try:
        return math.isclose(float(a), float(b), abs_tol=tol)
    except (TypeError, ValueError):
        return str(a) == str(b)


class Interface:
    """Base interface type. Subclasses declare ``PARAMS`` (constructor
    keyword names, in order) and ``ROLE`` (``male`` / ``female`` /
    ``neutral``)."""

    PARAMS: ClassVar[tuple] = ()
    ROLE: ClassVar[str] = "neutral"
    DOC: ClassVar[str] = ""
    # Rotation about the anchor +Z does not matter (holes, shafts, bearing
    # faces): loop checks ignore it and check() does not list it as a DOF.
    AXISYMMETRIC: ClassVar[bool] = False
    # Either way along the axis fits (a through bore): a loop closing on it
    # is checked both ways.
    REVERSIBLE: ClassVar[bool] = False
    # n-fold rotational symmetry about the anchor +Z (a 4-hole square pattern:
    # 4): a mate may clock in 360/n degree steps (``connect(..., clock=k)``)
    # and a loop closing on it snaps to the nearest step. Per instance:
    # ``PlaneFace(clock_symmetry=4)``.
    CLOCK_SYMMETRY: ClassVar[int] = 1

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        _TYPES[cls.__name__] = cls

    def __init__(
        self, *args: Any, clock_symmetry: Optional[int] = None, **params: Any
    ) -> None:
        names = list(self.PARAMS)
        if len(args) > len(names):
            raise TypeError(f"{type(self).__name__} takes {names}")
        values: Dict[str, Any] = {n: None for n in names}
        values.update(dict(zip(names, args)))
        for key in params:
            if key not in values and names:
                raise TypeError(
                    f"{type(self).__name__}: unknown parameter {key!r} (takes {names})"
                )
        values.update(params)
        self.params: Dict[str, Any] = {
            k: _jsonable(v) for k, v in values.items() if v is not None
        }
        if clock_symmetry is not None:
            n = clock_symmetry
            if isinstance(n, bool) or int(n) != n or n < 1:
                raise ValueError(
                    f"{type(self).__name__}: clock_symmetry must be a positive integer, got {n!r}"
                )
            if int(n) != type(self).CLOCK_SYMMETRY:
                self.params["clock_symmetry"] = int(n)

    @property
    def clock_symmetry(self) -> int:
        """n-fold symmetry about +Z (1: none); see ``CLOCK_SYMMETRY``."""
        return int(self.params.get("clock_symmetry", type(self).CLOCK_SYMMETRY))

    @property
    def type_name(self) -> str:
        return type(self).__name__

    @property
    def role(self) -> str:
        return self.ROLE

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_") or name == "params":
            raise AttributeError(name)
        if name in type(self).PARAMS or name in self.__dict__.get("params", {}):
            return self.__dict__["params"].get(name)
        raise AttributeError(f"{type(self).__name__} has no parameter {name!r}")

    def to_json(self) -> str:
        return json.dumps(self.params, sort_keys=True)

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, Interface)
            and other.type_name == self.type_name
            and other.params == self.params
        )

    def __hash__(self) -> int:
        return hash((self.type_name, self.to_json()))

    def __repr__(self) -> str:
        inner = ", ".join(f"{k}={v!r}" for k, v in self.params.items())
        return f"{self.type_name}({inner})"

    def describe(self) -> str:
        """``ScrewHole M5`` — the label viewers show."""
        main = next((v for k, v in self.params.items() if k != "clock_symmetry"), None)
        return self.type_name if main is None else f"{self.type_name} {main}"


def clock_step(a: Interface, b: Interface) -> Optional[float]:
    """Clocking step (radians) two interfaces share: ``2π / gcd(n_a, n_b)``
    of their clock symmetries (an axisymmetric side takes the other's);
    ``None`` when both are axisymmetric (any angle), ``2π`` when there is no
    common symmetry."""
    sa = None if a.AXISYMMETRIC else a.clock_symmetry
    sb = None if b.AXISYMMETRIC else b.clock_symmetry
    if sa is None and sb is None:
        return None
    n = sb if sa is None else sa if sb is None else math.gcd(sa, sb)
    return 2.0 * math.pi / n


def interface_type(name: str) -> Type[Interface]:
    """The registered interface class called ``name``; an unknown type gets a
    generic subclass (parameters kept as given), so a DAG from another
    library still loads."""
    cls = _TYPES.get(name)
    if cls is None:
        cls = type(name, (Interface,), {"PARAMS": (), "__module__": __name__})
    return cls


def interface_types() -> Dict[str, Type[Interface]]:
    return dict(_TYPES)


def from_params(type_name: str, params: Optional[Dict[str, Any]]) -> Interface:
    cls = interface_type(type_name)
    obj = cls.__new__(cls)
    obj.params = {k: _jsonable(v) for k, v in (params or {}).items()}
    return obj


# --------------------------------------------------------------------------- #
# Core vocabulary
# --------------------------------------------------------------------------- #


class ScrewHole(Interface):
    """A hole face a screw head, a washer or a nut lands on (+Z out of the
    face, the hole along -Z). ``depth``: material the screw passes / grips;
    ``thread``: tapped (``TappedHole(..., fastener=True)`` binds it so);
    ``drilled``: False when the connection must cut the clearance hole."""

    PARAMS = ("size", "depth", "thread", "drilled")
    ROLE = "female"
    AXISYMMETRIC = True


class ScrewHead(Interface):
    """Under-head seat of a screw (+Z down the shank). ``length`` under head."""

    PARAMS = ("size", "length")
    ROLE = "male"
    AXISYMMETRIC = True


class ScrewTip(Interface):
    """Shank end of a screw (+Z out of the tip)."""

    PARAMS = ("size",)
    ROLE = "male"
    AXISYMMETRIC = True


class NutSeat(Interface):
    """Bearing face of a nut / washer / spacer (+Z out of the face)."""

    PARAMS = ("size",)
    ROLE = "male"
    AXISYMMETRIC = True


class Bore(Interface):
    """A bore a shaft passes through or stops in (+Z along the bore)."""

    PARAMS = ("d", "fit")
    ROLE = "female"
    AXISYMMETRIC = True
    REVERSIBLE = True


class Shaft(Interface):
    """A shaft axis (+Z along the shaft, origin at its start)."""

    PARAMS = ("d",)
    ROLE = "male"
    AXISYMMETRIC = True
    REVERSIBLE = True


class ShaftEnd(Interface):
    """A shaft tip (+Z out of the end): mates into a ``Bore`` stop."""

    PARAMS = ("d",)
    ROLE = "male"
    AXISYMMETRIC = True


class BearingSeat(Interface):
    """A pocket shoulder a rolling bearing sits on (+Z toward the opening)."""

    PARAMS = ("model",)
    ROLE = "female"
    AXISYMMETRIC = True


class BearingFace(Interface):
    """A bearing ring face (+Z outward); ``d`` = bore diameter."""

    PARAMS = ("model", "d")
    ROLE = "male"
    AXISYMMETRIC = True


class BearingPocket(Interface):
    """Mouth of a linear-bearing pocket for a rod of diameter ``rod`` (+Z into
    the pocket)."""

    PARAMS = ("rod", "model")
    ROLE = "female"
    AXISYMMETRIC = True


class RodHole(Interface):
    """Mouth of a hole a rod end is fixed in (+Z along the rod, into the axis)."""

    PARAMS = ("d",)
    ROLE = "female"
    AXISYMMETRIC = True


class RodEnd(Interface):
    """End face of a rod (+Z outward)."""

    PARAMS = ("d",)
    ROLE = "male"
    AXISYMMETRIC = True


class RodAxis(Interface):
    """Rod axis (+Z along the rod): linear bearings slide on it."""

    PARAMS = ("d",)
    ROLE = "male"
    AXISYMMETRIC = True
    REVERSIBLE = True


class NemaFace(Interface):
    """Motor mounting face of a bracket (+Z toward the motor)."""

    PARAMS = ("frame",)
    ROLE = "female"


class NemaBody(Interface):
    """Front face of a NEMA motor (+Z out along the shaft)."""

    PARAMS = ("frame",)
    ROLE = "male"


class TSlot(Interface):
    """A profile T-slot opening (+Z out of the face, +X along the profile)."""

    PARAMS = ("series", "slot")
    ROLE = "female"


class TSlotNutSeat(Interface):
    """Neck top of a T-slot nut (+Z out of the slot, flush with the face)."""

    PARAMS = ("slot",)
    ROLE = "male"


class PlaneFace(Interface):
    """A generic flat face (+Z outward): face-to-face mates."""

    PARAMS = ("name",)
    ROLE = "neutral"


# --------------------------------------------------------------------------- #
# Mechanisms and structures (kept minimal)
# --------------------------------------------------------------------------- #


class PivotPin(Interface):
    """A pivot pin / hinge axis (+Z along the pin, origin on the shoulder the
    mating link bears on): a ``PivotHole`` turns on it (revolute)."""

    PARAMS = ("d",)
    ROLE = "male"
    AXISYMMETRIC = True


class PivotHole(Interface):
    """A pivot bore of a link / lever (+Z out of the bearing face)."""

    PARAMS = ("d",)
    ROLE = "female"
    AXISYMMETRIC = True


class SlideRail(Interface):
    """A linear guide rail (+Z along the travel, +X up out of the rail top),
    origin at the travel zero: a ``SlideCarriage`` slides on it."""

    PARAMS = ("profile",)
    ROLE = "male"


class SlideCarriage(Interface):
    """The running frame of a carriage / slide block (+Z along its travel,
    +X up), origin where it sits at travel zero."""

    PARAMS = ("profile",)
    ROLE = "female"


class StructuralEnd(Interface):
    """End of a structural member (+Z out of the end, +X the section's
    strong axis). ``fixity``: ``"fixed"`` (moment connection) or
    ``"pinned"`` (no moment), for analysis; geometrically the end is
    fastened rigidly either way."""

    PARAMS = ("section", "fixity")
    ROLE = "neutral"
