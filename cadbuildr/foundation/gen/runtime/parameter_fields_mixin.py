"""ParameterFieldsMixin for parameter types."""

from typing import Any
from typing import get_origin, get_args


class ParameterFieldsMixin:
    """Mixin for auto-casting primitives to Parameter types on field assignment."""
    
    def __setattr__(self, name: str, value: Any) -> None:
        if hasattr(self, '__class__') and hasattr(self.__class__, 'model_fields'):
            if name in self.__class__.model_fields:
                field_info = self.__class__.model_fields[name]
                field_annotation = field_info.annotation
                origin = get_origin(field_annotation)
                if origin is not None:
                    args = get_args(field_annotation)
                    for arg in args:
                        if arg is not type(None):
                            field_annotation = arg
                            break
                if isinstance(field_annotation, type) and field_annotation.__name__.endswith('Parameter'):
                    if isinstance(value, field_annotation):
                        super().__setattr__(name, value)
                        return
                    if isinstance(value, (bool, int, float, str)):
                        if hasattr(field_annotation, '_cast'):
                            try:
                                casted = field_annotation._cast(value)
                                if isinstance(casted, dict):
                                    value = field_annotation(**casted)
                                elif isinstance(casted, field_annotation):
                                    value = casted
                                else:
                                    casted = {field_annotation.model_fields['value'].alias or 'value': casted}
                                    value = field_annotation(**casted)
                            except (TypeError, ValueError):
                                pass
        super().__setattr__(name, value)




