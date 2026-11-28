"""Public introspection of parts, assemblies and their anchors.

Libraries used private helpers for these (``compute_functions._anchor_owner``,
the ``_source_component`` attribute, ``interference._walk``); those keep
working, and this module is the supported way:

* :func:`owner_of` — the Part / Assembly an anchor (or interface) belongs to;
* :func:`source_of` — the live Python Part / Assembly behind a placed root
  (``assembly.components[i]`` is a ``PartRoot`` / ``AssemblyRoot``);
* :func:`component_extents` — the bounding box of a Part or Assembly in its
  own frame (``lo`` / ``hi``, plus the boxes and what could not be bounded).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

from .interference import OBB, estimate_part_extents

__all__ = ["ComponentExtents", "component_extents", "owner_of", "source_of"]


def owner_of(x: Any) -> Any:
    """The Part / Assembly that owns ``x``: an ``Anchor`` (registered with
    ``add_anchor``, or derived from one) or an ``Interface`` node.

    Raises ``ValueError`` for an anchor that was never attached.
    """
    from .compute_functions import _anchor_owner
    from .gen.models import Interface

    if isinstance(x, Interface):
        from .interfaces.connect import owner_of as interface_owner

        return interface_owner(x)
    if not hasattr(x, "frame") or not hasattr(x, "name"):
        raise TypeError(
            f"owner_of takes an Anchor or an Interface, got {type(x).__name__}"
        )
    return _anchor_owner(x)


def source_of(component: Any) -> Any:
    """The live Part / Assembly a placed ``PartRoot`` / ``AssemblyRoot`` was
    made from (edits to it reach the DAG). A Part / Assembly is returned as is;
    a root built directly (no Python source) is returned unchanged too."""
    from .compute_functions import _SOURCE_COMPONENT_ATTR

    return getattr(component, _SOURCE_COMPONENT_ATTR, None) or component


@dataclass(frozen=True)
class ComponentExtents:
    """Bounding box of a component, in the component's own frame (mm).

    ``lo`` / ``hi`` are the min / max corners of the axis-aligned box around
    every bounded solid (``None`` when nothing could be bounded). ``boxes``
    are the oriented boxes behind it; ``unknown`` names the parts (path:
    reason) that could not be bounded, so the box may miss them.
    """

    lo: Optional[tuple[float, float, float]]
    hi: Optional[tuple[float, float, float]]
    boxes: tuple[OBB, ...] = ()
    unknown: tuple[str, ...] = ()

    @property
    def known(self) -> bool:
        """True when every part was bounded."""
        return self.lo is not None and not self.unknown

    @property
    def size(self) -> Optional[tuple[float, float, float]]:
        if self.lo is None or self.hi is None:
            return None
        return tuple(h - l for l, h in zip(self.lo, self.hi))  # type: ignore[return-value]

    @property
    def center(self) -> Optional[tuple[float, float, float]]:
        if self.lo is None or self.hi is None:
            return None
        return tuple((l + h) / 2.0 for l, h in zip(self.lo, self.hi))  # type: ignore[return-value]


def component_extents(component: Any, *, text: bool = True) -> ComponentExtents:
    """Bounding box of a Part / Assembly (or a placed root) in its own frame.

    Parts are bounded as :func:`~cadbuildr.foundation.interference.estimate_part_extents`
    does (declared ``set_part_extents`` win); an assembly is the union of its
    placed parts. ``text`` bounds ``Text`` profiles with a font-free outer
    estimate (on by default here; ``check_interference`` keeps Text unknown).
    """
    from .gen.models import Assembly, AssemblyRoot

    if isinstance(component, (Assembly, AssemblyRoot)):
        from .interference import _walk

        leaves, _, _, _ = _walk(component, text=text)
        boxes = [b for leaf in leaves for b in leaf.world_boxes]
        unknown = [
            f"{leaf.path}: {', '.join(leaf.extents.unknown)}"
            for leaf in leaves
            if not leaf.extents.known
        ]
    else:
        ext = estimate_part_extents(component, text=text)
        boxes = list(ext.boxes)
        unknown = list(ext.unknown)
    if not boxes:
        return ComponentExtents(None, None, (), tuple(unknown) or ("no solid",))
    pts = np.vstack([b.corners() for b in boxes])
    lo = tuple(float(v) for v in pts.min(axis=0))
    hi = tuple(float(v) for v in pts.max(axis=0))
    return ComponentExtents(lo, hi, tuple(boxes), tuple(unknown))  # type: ignore[arg-type]
