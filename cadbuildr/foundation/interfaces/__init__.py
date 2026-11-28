"""Interfaces: typed mating sites, mate rules and ``connect``.

A part ships with its interfaces (semantic features create them, or
``part.add_interface(ScrewHole("M5", depth=8), anchor)``); an assembly joins
any two parts in one line, ``assembly.connect(a, b)``, with the joint the
mate rule table gives (:mod:`.rules`); ``assembly.check()`` reports what is
left unconnected, placed by coordinates, or no longer closing.

* types (:mod:`.types`): ``ScrewHole``, ``ScrewHead``, ``Shaft``, ``Bore``,
  ``BearingSeat``, ``RodHole``, ``NemaFace``, ``TSlot``, ``PlaneFace``,
  ``PivotPin`` / ``PivotHole``, ``SlideRail`` / ``SlideCarriage``,
  ``StructuralEnd``... (subclass :class:`Interface` for more; list-valued
  parameters and ``clock_symmetry=n`` are allowed);
* rules (:mod:`.rules`): ``@mate_rule(A, B, joint=..., equal=[...],
  limits=...)`` and :class:`Mate` (``at`` / ``rotate`` for computed
  placement); :func:`export_rules` is the declarative table;
* ``connect(a, b, limits=(lo, hi), clock=k, **dof_or_options)``: DOF values,
  joint limits, clocking by symmetry steps, and rule options;
* features (:mod:`.features`): ``RodHole``, ``BearingPocket``, ``NemaMount``,
  ``ShaftFeature`` and ``fastener=`` on the hole wizards (``TappedHole``
  binds a threaded ``ScrewHole``).
"""

from .types import *  # noqa: F401,F403
from .types import Interface, clock_step, interface_type, interface_types, same_value
from .rules import (
    JOINTS,
    LIMIT_FIELDS,
    AmbiguousConnect,
    IncompatibleInterfaces,
    LoopMismatch,
    UnsolvedLoop,
    Mate,
    MateContext,
    MateError,
    Rule,
    export_rules,
    find_rule,
    mate_rule,
    normalize_limits,
    rules,
)
from .connect import (
    loop_delta,
    candidate_pairs,
    check_assembly,
    interface_issues,
    interfaces_of,
    owner_of,
    spec_of,
    uses_interfaces,
)
from . import features

from .types import __all__ as _types_all

__all__ = [
    *_types_all,
    "JOINTS",
    "LIMIT_FIELDS",
    "AmbiguousConnect",
    "IncompatibleInterfaces",
    "LoopMismatch",
    "UnsolvedLoop",
    "Mate",
    "MateContext",
    "MateError",
    "Rule",
    "candidate_pairs",
    "clock_step",
    "check_assembly",
    "interface_issues",
    "export_rules",
    "features",
    "find_rule",
    "interfaces_of",
    "mate_rule",
    "normalize_limits",
    "owner_of",
    "rules",
    "spec_of",
    "uses_interfaces",
]
