from __future__ import annotations
from typing import Any


class SketchElementMixin:
    """
    Mixin for Pydantic v2 models that should auto-register with their sketch.
    Assumes the model has a `sketch` attribute (may be None for some types),
    and that `sketch.add_element(self)` is the registration API.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Passing a Plane where a Sketch is expected is a common slip; pydantic's
        # raw "instance of Sketch" error makes agents probe types instead of
        # fixing the call, so name the fix directly.
        from cadbuildr.foundation.gen.models import Plane

        if isinstance(kwargs.get("sketch"), Plane):
            name = type(self).__name__
            rest = ", ".join(f for f in type(self).model_fields if f != "sketch")
            raise TypeError(
                f"{name} needs a Sketch, not a Plane: use `{name}(Sketch(plane), {rest})`"
            )
        super().__init__(*args, **kwargs)

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
