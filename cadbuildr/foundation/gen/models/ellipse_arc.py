from __future__ import annotations
from typing import List, Optional, Any, Dict, Union, Iterable
from pydantic import BaseModel, Field, model_validator
from ..runtime import Computable, _eval_expr, run_method
from cadbuildr.foundation.mixin.sketch_mixin import SketchElementMixin
from cadbuildr.foundation.gen.runtime.parameter_fields_mixin import ParameterFieldsMixin
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .float_parameter import FloatParameter
    from .point import Point
    from .sketch import Sketch


class EllipseArc(SketchElementMixin, ParameterFieldsMixin, BaseModel, Computable):
    """Generated from GraphQL object EllipseArc."""

    # --- Positional-argument constructor shim --------------------- #
    def __init__(self, *args, **kwargs):
        """
        Allow instantiation like  SugarAmount(12.5)  or  SugarAmount("12.5").
        If both positional *and* keyword data are supplied we keep Pydantic's
        normal rules: positional is ignored and Pydantic will raise.
        """
        from ..runtime.init_helpers import _init_with_cast

        use_normal, processed_kwargs = _init_with_cast(
            self.__class__,
            args,
            kwargs,
            cast_info=None,
            field_order=["center", "a", "b", "start_angle", "end_angle"],
            list_fields=None,
        )
        if use_normal:
            super().__init__(*args, **kwargs)
        else:
            super().__init__(**processed_kwargs)

    def translate(self, dx: float, dy: float) -> Optional[EllipseArc]:
        # Build local namespace with parameters for method function
        _locals = {"dx": dx, "dy": dy}
        return run_method(self, "ellipse_arc_translate", _locals)

    def rotate(self, angle: float, center: Optional[Point] = None) -> Optional[EllipseArc]:
        # Build local namespace with parameters for method function
        _locals = {"angle": angle, "center": center}
        return run_method(self, "ellipse_arc_rotate", _locals)

    center: Point = Field(...)
    a: FloatParameter = Field(...)
    b: FloatParameter = Field(...)
    start_angle: FloatParameter = Field(...)
    end_angle: FloatParameter = Field(...)
    sketch: Optional[Sketch] = Field(
        default=None, json_schema_extra={"compute": {"expr": "center.sketch"}}
    )

    model_config = {"protected_namespaces": (), "extra": "allow"}  # Pydantic v2 config
