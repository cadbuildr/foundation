"""Library configurables: parts, assemblies and operations a viewer can insert.

A library declares each configurable once, with a decorator and type hints::

    from cadbuildr.foundation.library import part, assembly, OneOf, InputOf, Num

    @part(category="Bearings/Ball", name="Deep groove ball bearing", standard="ISO 15")
    class DeepGrooveBearing(Part):
        TABLE = {"608": {"d": 8, "D": 22, "B": 7}, ...}
        def __init__(self, model: OneOf[TABLE] = "608"): ...

    @assembly(category="Demo")
    class Skateboard(Assembly):
        def __init__(self, bearing: InputOf[DeepGrooveBearing, "model"] = "608"):
            DeepGrooveBearing(model=bearing)     # bound to the `bearing` input

The registry turns declarations into a ``cadbuildr.library-manifest/1``
document (:func:`get_manifest`); every instance of a decorated class carries a
``LibraryRef`` (item, inputs, configuration, bindings, source) that lands in
the DAG as the ``library`` dep of its PartRoot / AssemblyRoot.

CLI: ``python -m cadbuildr.foundation.library {manifest,eval,insert,sources} ...``.
Libraries are ordinary Python distributions declaring the entry point group
``cadbuildr.libraries``; project dependencies are managed with uv (see :mod:`.sources`).
"""

from .hints import Color, InputOf, Num, OneOf, humanize, widget_for
from .registry import (
    MANIFEST_FORMAT,
    LibraryItem,
    assembly,
    discover,
    find_item,
    get_manifest,
    item_for,
    items,
    operation,
    part,
)
from .sources import activate, purge
from .stamp import stamp_of
from .evaluate import evaluate

__all__ = [
    "MANIFEST_FORMAT",
    "Color",
    "InputOf",
    "LibraryItem",
    "Num",
    "OneOf",
    "activate",
    "assembly",
    "discover",
    "evaluate",
    "find_item",
    "get_manifest",
    "humanize",
    "item_for",
    "items",
    "operation",
    "part",
    "purge",
    "stamp_of",
    "widget_for",
]
