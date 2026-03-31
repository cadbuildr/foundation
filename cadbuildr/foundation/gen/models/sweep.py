from __future__ import annotations
from typing import List, Optional, Any, Dict, Union, Iterable
from pydantic import BaseModel, Field, model_validator
from ..runtime import Computable, _eval_expr, run_method
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .helix3_d import Helix3D
    from .sketch import Sketch
    from .unions import ClosedShape2D

class Sweep(BaseModel, Computable):
    """Generated from GraphQL object Sweep."""


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
            field_order=['profile', 'path'],
            list_fields=None,
        )
        if use_normal:
            super().__init__(*args, **kwargs)
        else:
            super().__init__(**processed_kwargs)






    profile: ClosedShape2D = Field(...)
    path: Helix3D = Field(...)
    sketch: Optional[Sketch] = Field(default=None, json_schema_extra={'compute': {'fn': 'compute_sweep_sketch', 'includeInDag': True}})

    model_config = {"protected_namespaces": (), "extra": "allow"}  # Pydantic v2 config