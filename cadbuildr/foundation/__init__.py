"""CADbuildr Foundation - Core types for parametric CAD (auto-generated from GraphQL schema)."""

# Re-export all generated types dynamically
from .gen.models import *
from .gen.runtime import *

# Import compute functions to register them
from . import compute_functions  # noqa: F401

# Import shape transformation methods to register them
from . import shape_methods  # noqa: F401

# Import helpers to add monkey-patched methods
from . import helpers  # noqa: F401

# Export PlaneFactory for backward compatibility
from .helpers import PlaneFactory, TFHelper

# Export pattern classes
from .pattern import CircularPattern, RectangularPattern

# DAG and WebRTC utilities
from .dag_utils import show, show_dag
from .coms.utils_webrtc import (
    set_port,
    set_broker_url,
    get_build_status,
    get_screenshot,
    wait_for_feedback,
    collect_and_display_feedback,
)
from .coms.kernel_api import KernelApiClient, KernelApiError


# Helpful error hints for unknown-symbol imports (PEP 562).
#
# Models repeatedly try `from cadbuildr.foundation import show_dag` (22/46
# of 14B L1 failures on 2026-04-22 run) and similar hallucinated symbols
# (Rectangle, Point, Helix). The bare `cannot import name X` error gives
# them no recovery path and they loop. This hook points them at the right
# submodule or the closest top-level match instead.
def __getattr__(name: str):
    import difflib
    import sys

    # Dunder / sunder / private lookups shortcut — no one benefits from a
    # hint for `__path__` or `_pytest_something`, and producing one for
    # every probe spams stderr during introspection.
    if name.startswith("_"):
        raise AttributeError(f"module 'cadbuildr.foundation' has no attribute {name!r}")

    mod = sys.modules[__name__]

    # Search already-imported submodules for an exact symbol match.
    prefix = __name__ + "."
    found_in: list[str] = []
    for modname, module in list(sys.modules.items()):
        if modname == __name__ or not modname.startswith(prefix):
            continue
        try:
            if hasattr(module, name):
                found_in.append(modname)
        except Exception:
            continue

    # Close-match suggestions against top-level public API.
    available = [n for n in dir(mod) if not n.startswith("_")]
    close = difflib.get_close_matches(name, available, n=3, cutoff=0.6)

    hints: list[str] = []
    if found_in:
        # Prefer the shortest module path (closest to foundation root).
        found_in.sort(key=len)
        hints.append(
            "exists in submodule(s): "
            + ", ".join(f"`from {mn} import {name}`" for mn in found_in[:3])
        )
    if close:
        hints.append(
            "close top-level names: " + ", ".join(close)
        )
    hints.append("see the foundation-cheatsheet skill for the public API")
    hint_msg = " | ".join(hints)

    # Python's `from X import Y` machinery swallows AttributeError messages
    # and replaces them with a terse default ImportError. To make sure the
    # model actually *sees* our hint, also emit it to stderr — that survives
    # the wrap and shows up in the agent's tool output. CPython calls
    # __getattr__ twice during `from X import Y` (once for the attr lookup,
    # once after the submodule-import fallback), so dedupe via a per-process
    # set to keep stderr clean.
    _emitted: set = globals().setdefault("_cadbuildr_foundation_hint_emitted", set())
    if name not in _emitted:
        _emitted.add(name)
        try:
            sys.stderr.write(
                f"[cadbuildr.foundation] import hint for {name!r}: {hint_msg}\n"
            )
            sys.stderr.flush()
        except Exception:
            pass

    raise AttributeError(
        f"module 'cadbuildr.foundation' has no attribute {name!r}. " + hint_msg
    )
