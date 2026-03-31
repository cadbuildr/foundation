from __future__ import annotations
from typing import List, Optional, Any, Dict, Union, Iterable
from pydantic import BaseModel, Field, model_validator
from ..runtime import Computable, _eval_expr, run_method
from cadbuildr.foundation.gen.runtime.parameter_fields_mixin import ParameterFieldsMixin
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .bool_parameter import BoolParameter
    from .frame import Frame
    from .string_parameter import StringParameter

class Plane(ParameterFieldsMixin, BaseModel, Computable):
    """Generated from GraphQL object Plane."""


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
            field_order=['frame', 'name'],
            list_fields=None,
        )
        if use_normal:
            super().__init__(*args, **kwargs)
        else:
            super().__init__(**processed_kwargs)




    def get_parallel_plane(self, distance: float, name: Optional[str]='parallel') -> Optional[Plane]:
        # Build local namespace with parameters for method function
        _locals = {
            'distance': distance,
            'name': name
        }
        return run_method(self, 'get_parallel_plane_method', _locals)
    def get_x_axis(self) -> Optional[List[float]]:
        return run_method(self, 'get_plane_x_axis')
    def get_y_axis(self) -> Optional[List[float]]:
        return run_method(self, 'get_plane_y_axis')
    def get_z_axis(self) -> Optional[List[float]]:
        return run_method(self, 'get_plane_z_axis')
    def get_angle_plane_from_axis(self, axis: List[float], angle: float, name: Optional[str]='rotated') -> Optional[Plane]:
        # Build local namespace with parameters for method function
        _locals = {
            'axis': axis,
            'angle': angle,
            'name': name
        }
        return run_method(self, 'get_angle_plane_from_axis_method', _locals)


    frame: Frame = Field(...)
    name: StringParameter = Field(...)
    display: BoolParameter = Field(default_factory=lambda: _eval_expr({}, 'BoolParameter(value=False)'), json_schema_extra={'default': {'expr': 'BoolParameter(value=False)'}})

    model_config = {"protected_namespaces": (), "extra": "allow"}  # Pydantic v2 config