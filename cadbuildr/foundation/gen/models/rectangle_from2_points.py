from __future__ import annotations
from typing import List, Optional, Any, Dict, Union, Iterable
from pydantic import BaseModel, Field, model_validator
from ..runtime import Computable, Expandable, _eval_expr, run_method
from cadbuildr.foundation.mixin.sketch_mixin import SketchElementMixin
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .point import Point
    from .rectangle import Rectangle
    from .sketch import Sketch

class RectangleFrom2Points(SketchElementMixin, BaseModel, Computable, Expandable):
    """Generated from GraphQL object RectangleFrom2Points."""


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
            field_order=['p1', 'p3', 'sketch'],
            list_fields=None,
        )
        if use_normal:
            super().__init__(*args, **kwargs)
        else:
            super().__init__(**processed_kwargs)






    p1: Point = Field(...)
    p3: Point = Field(...)
    sketch: Sketch = Field(...)
    p2: Optional[Point] = Field(default=None, json_schema_extra={'compute': {'expr': 'Point(sketch=sketch, x=p3.x, y=p1.y)'}})
    p4: Optional[Point] = Field(default=None, json_schema_extra={'compute': {'expr': 'Point(sketch=sketch, x=p1.x, y=p3.y)'}})
    result: Optional[Rectangle] = Field(default=None, json_schema_extra={'expand': {'into': {'p1': '$p1', 'p2': '$p2', 'p3': '$p3', 'p4': '$p4'}}})

    model_config = {"protected_namespaces": (), "extra": "allow"}  # Pydantic v2 config