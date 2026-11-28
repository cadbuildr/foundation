"""Semantic features: geometry that ships with its interface.

Each feature cuts its geometry into the part that owns ``face`` (an anchor
registered on the part, +Z out of the face unless noted) and binds the
interface(s) a mate needs, so the result is immediately connectable::

    RodHole(face=self.anchor("rod_hole_a"), d=8, depth=10)        # hole + RodHole
    BearingPocket(face=self.anchor("inner_face"), model="608")    # counterbore + BearingSeat
    NemaMount(face=self.anchor("motor_face"), frame="NEMA17", depth=10)
    ShaftFeature(self, d=8, length=100)                           # Shaft + 2 x ShaftEnd

``Hole`` / ``CounterBoreHole`` / ``CounterSinkHole`` / ``ClearanceHole`` /
``TappedHole`` take ``fastener="M5"`` (with an anchor) to bind a ``ScrewHole``
the same way (``group=`` too); ``fastener=True`` takes the size from the
wizard's ``size`` / ``thread_size``. A ``TappedHole`` binds a threaded
``ScrewHole(thread=True)``: a screw driven into it needs no grip length::

    TappedHole(anchor=a, thread_size=5, depth=10, fastener=True)  # ScrewHole M5, thread
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

from ..compute_functions import _anchor_owner, tf_in_component
from ..gen.models import Circle, Extrusion, Point, Sketch
from ..helpers import anchor_plane, make_anchor
from ..math_utils import axis_angle_to_quaternion, compose_tf
from . import types as T

__all__ = ["BEARINGS", "NEMA", "BearingPocket", "NemaMount", "RodHole", "ShaftFeature"]

# ISO 15 deep groove bearings: bore d, outer D, width B.
BEARINGS: Dict[str, Dict[str, float]] = {
    "623": {"d": 3.0, "D": 10.0, "B": 4.0},
    "624": {"d": 4.0, "D": 13.0, "B": 5.0},
    "625": {"d": 5.0, "D": 16.0, "B": 5.0},
    "626": {"d": 6.0, "D": 19.0, "B": 6.0},
    "688": {"d": 8.0, "D": 16.0, "B": 5.0},
    "608": {"d": 8.0, "D": 22.0, "B": 7.0},
    "6800": {"d": 10.0, "D": 19.0, "B": 5.0},
    "6801": {"d": 12.0, "D": 21.0, "B": 5.0},
}

# NEMA frames: hole pitch, boss diameter, hole (screw) diameter.
NEMA: Dict[str, Dict[str, float]] = {
    "NEMA14": {"pitch": 26.0, "boss_d": 22.0, "hole_d": 3.0},
    "NEMA17": {"pitch": 31.0, "boss_d": 22.0, "hole_d": 3.0},
    "NEMA23": {"pitch": 47.14, "boss_d": 38.1, "hole_d": 5.0},
}

_FLIP_X = axis_angle_to_quaternion([1.0, 0.0, 0.0], math.pi)


def _cut(
    anchor: Any, r: float, z0: float, z1: float, at: Sequence[float] = (0.0, 0.0)
) -> Any:
    sketch = Sketch(anchor_plane(anchor))
    shape = Circle(Point(sketch, float(at[0]), float(at[1])), float(r))
    return Extrusion(shape, float(z0), float(z1), cut=True)


def _derived(
    owner: Any, base: Any, name: str, offset: Sequence[float], flip: bool = False
) -> Any:
    """A registered anchor of ``owner`` at ``offset`` in ``base``'s frame
    (rotated 180 deg about X when ``flip``)."""
    t, q = tf_in_component(base.frame, owner)
    t, q = compose_tf(
        t, q, [float(v) for v in offset], _FLIP_X if flip else [1.0, 0.0, 0.0, 0.0]
    )
    return owner.add_anchor(make_anchor(name, t, q))


class _Feature:
    def __init__(self) -> None:
        self.interfaces: List[Any] = []
        self.operations: List[Any] = []

    @property
    def interface(self) -> Any:
        return self.interfaces[0]

    def _apply(self, owner: Any) -> None:
        owner.add_operations(self.operations)


class RodHole(_Feature):
    """A hole a rod end is fixed in. ``face``: the hole mouth, +Z along the
    hole *into* the material (the rod's direction); cut ``0 .. depth``."""

    def __init__(
        self,
        face: Any,
        d: float,
        depth: float,
        *,
        clearance: float = 0.0,
        required: bool = False,
    ) -> None:
        super().__init__()
        owner = _anchor_owner(face)
        self.operations.append(
            _cut(face, float(d) / 2.0 + clearance, 0.0, float(depth))
        )
        self._apply(owner)
        self.interfaces.append(
            owner.add_interface(T.RodHole(d=float(d)), face, required=required)
        )


class BearingPocket(_Feature):
    """A rolling-bearing seat: counterbore (bearing ``D`` x ``B``) from
    ``face`` (+Z out of the face), plus a ``through_d`` hole down to
    ``depth``, at ``at`` (u, v) in the face plane. Binds ``BearingSeat(model)`` on the shoulder (+Z toward the
    opening), anchor ``name``."""

    def __init__(
        self,
        face: Any,
        model: str,
        *,
        at: Sequence[float] = (0.0, 0.0),
        name: Optional[str] = None,
        depth: Optional[float] = None,
        through_d: Optional[float] = None,
        D: Optional[float] = None,
        B: Optional[float] = None,
    ) -> None:
        super().__init__()
        owner = _anchor_owner(face)
        spec = BEARINGS.get(str(model), {})
        D = float(D if D is not None else spec["D"])
        B = float(B if B is not None else spec["B"])
        u, v = float(at[0]), float(at[1])
        self.operations.append(_cut(face, D / 2.0, -B, 0.0, (u, v)))
        if through_d and depth and depth > B:
            self.operations.append(
                _cut(face, float(through_d) / 2.0, -float(depth), -B, (u, v))
            )
        self._apply(owner)
        seat = _derived(owner, face, name or f"{face.name.value}_seat", (u, v, -B))
        self.interfaces.append(
            owner.add_interface(T.BearingSeat(model=str(model)), seat)
        )


class NemaMount(_Feature):
    """A NEMA motor mount on ``face`` (+Z toward the motor): boss hole and
    four screw holes through ``depth``. Binds ``NemaFace(frame)`` on ``face``
    and four ``ScrewHole`` (group ``group``) whose anchors ``hole_names``
    sit on the far face (``screws="far"``, heads opposite the motor) or on
    ``face``; holes are numbered over the screw-side face frame, X then Y."""

    def __init__(
        self,
        face: Any,
        frame: str,
        depth: float,
        *,
        group: str = "motor",
        hole_names: str = "motor_hole_{i}",
        screws: str = "far",
        pitch: Optional[float] = None,
        boss_d: Optional[float] = None,
        hole_d: Optional[float] = None,
        clearance: float = 0.2,
    ) -> None:
        super().__init__()
        owner = _anchor_owner(face)
        spec = NEMA.get(str(frame), {})
        pitch = float(pitch if pitch is not None else spec["pitch"])
        boss_d = float(boss_d if boss_d is not None else spec["boss_d"])
        hole_d = float(hole_d if hole_d is not None else spec["hole_d"])
        depth = float(depth)
        self.operations.append(_cut(face, boss_d / 2.0 + 0.5, -depth, 0.0))
        hp = pitch / 2.0
        far = screws == "far"
        spots = [
            (sx * hp, (-sy if far else sy) * hp) for sx in (-1, 1) for sy in (-1, 1)
        ]
        for u, v in spots:
            self.operations.append(
                _cut(face, hole_d / 2.0 + clearance, -depth, 0.0, (u, v))
            )
        self._apply(owner)
        self.interfaces.append(owner.add_interface(T.NemaFace(frame=str(frame)), face))
        size = f"M{hole_d:g}"
        for i, (u, v) in enumerate(spots):
            anchor = _derived(
                owner,
                face,
                hole_names.format(i=i),
                (u, v, -depth if far else 0.0),
                flip=far,
            )
            self.interfaces.append(
                owner.add_interface(
                    T.ScrewHole(size=size, depth=depth), anchor, group=group
                )
            )


class ShaftFeature(_Feature):
    """Shaft interfaces of a body of revolution built along +Z from 0 to
    ``length``: ``Shaft(d)`` on ``axis`` and ``ShaftEnd(d)`` on both ends
    (anchors made when missing). ``geometry=True`` also extrudes the shaft."""

    def __init__(
        self,
        part: Any,
        d: float,
        length: float,
        *,
        axis: str = "axis",
        ends: Sequence[str] = ("end_a", "end_b"),
        geometry: bool = False,
    ) -> None:
        super().__init__()
        d, length = float(d), float(length)
        if geometry:
            sketch = Sketch(part.xy())
            part.add_operation(
                Extrusion(Circle(Point(sketch, 0.0, 0.0), d / 2.0), length)
            )
        names = {a.name.value: a for a in part.anchors}
        poses = {
            axis: ((0, 0, 0), False),
            ends[0]: ((0, 0, 0), True),
            ends[1]: ((0, 0, length), False),
        }
        anchors = {}
        for n, (pos, down) in poses.items():
            anchors[n] = names.get(n) or part.add_anchor(
                make_anchor(n, pos, z_down=down)
            )
        self.interfaces.append(part.add_interface(T.Shaft(d=d), anchors[axis]))
        for n in ends:
            self.interfaces.append(part.add_interface(T.ShaftEnd(d=d), anchors[n]))


def _install_fastener_holes() -> None:
    from ..gen.models import (
        Anchor,
        ClearanceHole,
        CounterBoreHole,
        CounterSinkHole,
        Hole,
        TappedHole,
    )

    def _value(obj: Any, name: str) -> Any:
        return getattr(getattr(obj, name, None), "value", None)

    def _size(hole: Any, fastener: Any) -> str:
        if fastener is not True:
            return str(fastener)
        nominal = _value(hole, "thread_size") or _value(hole, "size")
        if nominal is None:
            raise TypeError(
                f"{type(hole).__name__}(fastener=True) needs a nominal size; "
                'pass fastener="M5"'
            )
        return f"M{float(nominal):g}"

    for cls in (Hole, CounterBoreHole, CounterSinkHole, TappedHole, ClearanceHole):
        original = cls.__init__
        tapped = cls is TappedHole

        def __init__(
            self: Any, *args: Any, __original=original, __tapped=tapped, **kwargs: Any
        ) -> None:
            fastener = kwargs.pop("fastener", None)
            group = kwargs.pop("group", None)
            anchor = kwargs.get("anchor")
            if anchor is None and args and isinstance(args[0], Anchor):
                anchor = args[0]
            if anchor is None and isinstance(kwargs.get("point"), Anchor):
                anchor = kwargs["point"]
            __original(self, *args, **kwargs)
            if fastener is None or fastener is False:
                return
            if anchor is None:
                raise TypeError(
                    f"{type(self).__name__}(fastener=...) needs the hole's anchor "
                    "(anchor=part.add_anchor(...)): the ScrewHole interface sits on it"
                )
            depth = _value(self, "depth")
            spec = T.ScrewHole(
                size=_size(self, fastener),
                depth=depth,
                thread=True if __tapped else None,
            )
            _anchor_owner(anchor).add_interface(spec, anchor, group=group)

        __init__.__doc__ = original.__doc__
        setattr(cls, "__init__", __init__)


_install_fastener_holes()
