from __future__ import annotations
from typing import List, Optional, Any, Dict, Union, Iterable
from pydantic import BaseModel, Field, model_validator
from ..runtime import Computable, _eval_expr, run_method

class FixedTranslationConstraint(BaseModel, Computable):
    """Generated from GraphQL object FixedTranslationConstraint."""


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
            field_order=['component', 'translation', 'quaternion'],
            list_fields={'translation', 'quaternion'},
        )
        if use_normal:
            super().__init__(*args, **kwargs)
        else:
            super().__init__(**processed_kwargs)






    component: Any = Field(...)
    translation: List[float] = Field(default_factory=lambda: _eval_expr({}, '[0.0, 0.0, 0.0]'), json_schema_extra={'default': {'expr': '[0.0, 0.0, 0.0]'}})
    quaternion: List[float] = Field(default_factory=lambda: _eval_expr({}, '[1.0, 0.0, 0.0, 0.0]'), json_schema_extra={'default': {'expr': '[1.0, 0.0, 0.0, 0.0]'}})

    model_config = {"protected_namespaces": (), "extra": "allow"}  # Pydantic v2 config