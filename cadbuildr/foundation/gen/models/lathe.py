from __future__ import annotations
from typing import List, Optional, Any, Dict, Union, Iterable
from pydantic import BaseModel, Field, model_validator
from ..runtime import Computable, _eval_expr, run_method
from cadbuildr.foundation.gen.runtime.parameter_fields_mixin import ParameterFieldsMixin
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .axis import Axis
    from .bool_parameter import BoolParameter
    from .sketch import Sketch
    from .unions import ClosedShape2D

class Lathe(ParameterFieldsMixin, BaseModel, Computable):
    """Generated from GraphQL object Lathe."""


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
            field_order=['shape', 'axis'],
            list_fields=None,
        )
        if use_normal:
            super().__init__(*args, **kwargs)
        else:
            super().__init__(**processed_kwargs)






    shape: ClosedShape2D = Field(...)
    axis: Axis = Field(...)
    cut: BoolParameter = Field(default_factory=lambda: _eval_expr({}, 'BoolParameter(value=False)'), json_schema_extra={'default': {'expr': 'BoolParameter(value=False)'}})
    sketch: Optional[Sketch] = Field(default=None, json_schema_extra={'compute': {'expr': 'shape.sketch', 'includeInDag': True}})

    model_config = {"protected_namespaces": (), "extra": "allow"}  # Pydantic v2 config