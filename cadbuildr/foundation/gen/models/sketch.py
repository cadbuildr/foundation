from __future__ import annotations
from typing import List, Optional, Any, Dict, Union, Iterable
from pydantic import BaseModel, Field, model_validator
from ..runtime import Computable, _eval_expr, run_method
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .plane import Plane
    from .point import Point
    from .unions import Shape2D

class Sketch(BaseModel, Computable):
    """Generated from GraphQL object Sketch."""


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
            field_order=['plane'],
            list_fields={'elements'},
        )
        if use_normal:
            super().__init__(*args, **kwargs)
        else:
            super().__init__(**processed_kwargs)




    def add_element(self, element: Shape2D) -> Optional[bool]:
        # Build local namespace with parameters for method function
        _locals = {
            'element': element
        }
        return run_method(self, 'add_element_method', _locals)


    plane: Plane = Field(...)
    elements: List[Shape2D] = Field(default_factory=lambda: _eval_expr({}, '[]'), json_schema_extra={'default': {'expr': '[]'}})
    origin: Optional[Point] = Field(default=None, json_schema_extra={'compute': {'fn': 'get_sketch_origin', 'includeInDag': True}})

    model_config = {"protected_namespaces": (), "extra": "allow"}  # Pydantic v2 config