from __future__ import annotations
from typing import List, Optional, Any, Dict, Union, Iterable
from pydantic import BaseModel, Field, model_validator
from ..runtime import Computable, Expandable, _eval_expr, run_method
from cadbuildr.foundation.gen.runtime.parameter_fields_mixin import ParameterFieldsMixin
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .extrusion import Extrusion
    from .float_parameter import FloatParameter
    from .point import Point

class Hole(ParameterFieldsMixin, BaseModel, Computable, Expandable):
    """Generated from GraphQL object Hole."""


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
            field_order=['point', 'radius', 'depth'],
            list_fields=None,
        )
        if use_normal:
            super().__init__(*args, **kwargs)
        else:
            super().__init__(**processed_kwargs)






    point: Point = Field(...)
    radius: FloatParameter = Field(...)
    depth: FloatParameter = Field(...)
    other_depth: FloatParameter = Field(default_factory=lambda: _eval_expr({}, 'FloatParameter(value=0.0)'), json_schema_extra={'default': {'expr': 'FloatParameter(value=0.0)'}})
    result: Optional[Extrusion] = Field(default=None, json_schema_extra={'expand': {'into': {'shape': [{'__typename': 'Circle', 'center': '$point', 'radius': '$radius'}], 'end': '$depth', 'start': '$other_depth', 'cut': {'__typename': 'BoolParameter', 'value': True}}}})

    model_config = {"protected_namespaces": (), "extra": "allow"}  # Pydantic v2 config