from __future__ import annotations
from typing import List, Optional, Any, Dict, Union, Iterable
from pydantic import BaseModel, Field, model_validator
from ..runtime import Computable, Expandable, _eval_expr, run_method
from cadbuildr.foundation.gen.runtime.parameter_fields_mixin import ParameterFieldsMixin
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .bool_parameter import BoolParameter
    from .float_parameter import FloatParameter
    from .helix3_d import Helix3D
    from .point3_d import Point3D
    from .sweep import Sweep
    from .unions import ClosedShape2D

class Thread(ParameterFieldsMixin, BaseModel, Computable, Expandable):
    """Generated from GraphQL object Thread."""


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
            field_order=['profile', 'pitch', 'height', 'radius', 'center', 'dir', 'lefthand'],
            list_fields=None,
        )
        if use_normal:
            super().__init__(*args, **kwargs)
        else:
            super().__init__(**processed_kwargs)






    profile: ClosedShape2D = Field(...)
    pitch: FloatParameter = Field(...)
    height: FloatParameter = Field(...)
    radius: FloatParameter = Field(...)
    center: Point3D = Field(default_factory=lambda: _eval_expr({}, 'Point3D(x=FloatParameter(value=0.0), y=FloatParameter(value=0.0), z=FloatParameter(value=0.0))'), json_schema_extra={'default': {'expr': 'Point3D(x=FloatParameter(value=0.0), y=FloatParameter(value=0.0), z=FloatParameter(value=0.0))'}})
    dir: Point3D = Field(default_factory=lambda: _eval_expr({}, 'Point3D(x=FloatParameter(value=0.0), y=FloatParameter(value=0.0), z=FloatParameter(value=1.0))'), json_schema_extra={'default': {'expr': 'Point3D(x=FloatParameter(value=0.0), y=FloatParameter(value=0.0), z=FloatParameter(value=1.0))'}})
    lefthand: BoolParameter = Field(default_factory=lambda: _eval_expr({}, 'BoolParameter(value=False)'), json_schema_extra={'default': {'expr': 'BoolParameter(value=False)'}})
    path: Optional[Helix3D] = Field(default=None, json_schema_extra={'compute': {'fn': 'compute_thread_path'}})
    result: Optional[Sweep] = Field(default=None, json_schema_extra={'expand': {'into': {'profile': '$profile', 'path': '$path'}}})

    model_config = {"protected_namespaces": (), "extra": "allow"}  # Pydantic v2 config