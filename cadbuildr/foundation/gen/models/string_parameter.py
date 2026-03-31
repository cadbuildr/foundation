from __future__ import annotations
from typing import List, Optional, Any, Dict, Union, Iterable
from pydantic import BaseModel, Field, model_validator
from cadbuildr.foundation.gen.runtime.parameter_fields_mixin import ParameterFieldsMixin

class StringParameter(ParameterFieldsMixin, BaseModel):
    """Generated from GraphQL object StringParameter."""


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
            cast_info={'field': 'value', 'scalars': ['Float', 'Int', 'String', 'Boolean', 'ID'], 'expr': None, 'fn': None},
            field_order=None,
            list_fields=None,
        )
        if use_normal:
            super().__init__(*args, **kwargs)
        else:
            super().__init__(**processed_kwargs)


    @model_validator(mode="before")
    @classmethod
    def _cast(cls, v):
        from ..runtime.cast_helpers import _cast_value_generic
        return _cast_value_generic(cls, v, 'value', ['Float', 'Int', 'String', 'Boolean', 'ID'])




    value: str = Field(...)

    model_config = {"protected_namespaces": ()}  # Pydantic v2 config