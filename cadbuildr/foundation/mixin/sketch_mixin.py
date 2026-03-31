from __future__ import annotations
from typing import Any


class SketchElementMixin:
    """
    Mixin for Pydantic v2 models that should auto-register with their sketch.
    Assumes the model has a `sketch` attribute (may be None for some types),
    and that `sketch.add_element(self)` is the registration API.
    """

    def model_post_init(self, __context: Any) -> None:
        # Respect parent's post-init if it exists
        super_method = getattr(super(), "model_post_init", None)
        if callable(super_method):
            super_method(__context)

        sketch = getattr(self, "sketch", None)
        if sketch is None:
            return

        # Best-effort registration; don't crash if missing method
        add = getattr(sketch, "add_element", None)
        if callable(add):
            add(self)
