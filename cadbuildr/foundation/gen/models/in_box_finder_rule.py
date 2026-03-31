from __future__ import annotations
from typing import List, Optional, Any, Dict, Union, Iterable
from pydantic import BaseModel, Field, model_validator
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .point3_d import Point3D

class InBoxFinderRule(BaseModel):
    """Generated from GraphQL object InBoxFinderRule."""


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
            field_order=['corner1', 'corner2'],
            list_fields=None,
        )
        if use_normal:
            super().__init__(*args, **kwargs)
        else:
            super().__init__(**processed_kwargs)






    corner1: Point3D = Field(...)
    corner2: Point3D = Field(...)

    model_config = {"protected_namespaces": ()}  # Pydantic v2 config