from __future__ import annotations
from typing import List, Optional, Any, Dict, Union, Iterable
from pydantic import BaseModel, Field, model_validator
from ..runtime import Computable, _eval_expr, run_method
from cadbuildr.foundation.gen.runtime.parameter_fields_mixin import ParameterFieldsMixin
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .bool_parameter import BoolParameter
    from .float_parameter import FloatParameter
    from .point3_d import Point3D

class Helix3D(ParameterFieldsMixin, BaseModel, Computable):
    """Generated from GraphQL object Helix3D."""


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
            field_order=['pitch', 'height', 'radius', 'center', 'dir', 'lefthand'],
            list_fields=None,
        )
        if use_normal:
            super().__init__(*args, **kwargs)
        else:
            super().__init__(**processed_kwargs)






    pitch: FloatParameter = Field(...)
    height: FloatParameter = Field(...)
    radius: FloatParameter = Field(...)
    center: Point3D = Field(...)
    dir: Point3D = Field(...)
    lefthand: BoolParameter = Field(default_factory=lambda: _eval_expr({}, 'BoolParameter(value=False)'), json_schema_extra={'default': {'expr': 'BoolParameter(value=False)'}})

    model_config = {"protected_namespaces": (), "extra": "allow"}  # Pydantic v2 config