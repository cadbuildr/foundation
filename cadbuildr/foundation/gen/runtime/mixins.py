"""Base mixin classes for generated types."""

from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, model_validator
from .cast_helpers import _cast_value_generic, _cast_with_expr, _cast_with_fn
from .init_helpers import _init_with_cast


class CastableMixin(BaseModel):
    """Mixin for types with @cast directive.
    
    This mixin provides __init__ and _cast methods for types that use the @cast directive.
    The actual casting logic is determined by the cast_info passed to __init__.
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize with cast support.
        
        This method expects 'cast_info', 'field_order', and 'list_fields' to be
        passed as keyword arguments (they will be removed before calling super().__init__).
        """
        # Extract cast/ordered metadata from kwargs
        cast_info = kwargs.pop('_cast_info', None)
        field_order = kwargs.pop('_field_order', None)
        list_fields = kwargs.pop('_list_fields', None)
        
        # Use the init helper to process args/kwargs
        use_normal, processed_kwargs = _init_with_cast(
            self.__class__,
            args,
            kwargs,
            cast_info=cast_info,
            field_order=field_order,
            list_fields=list_fields,
        )
        
        if use_normal:
            super().__init__(*args, **kwargs)
        else:
            super().__init__(**processed_kwargs)
    
    @classmethod
    def _get_cast_info(cls) -> Optional[Dict[str, Any]]:
        """Get cast information for this class.
        
        This should be overridden by generated classes to return their cast_info.
        """
        return getattr(cls, '_cast_info', None)
    
    @model_validator(mode="before")
    @classmethod
    def _cast(cls, v: Any) -> Dict[str, Any]:
        """Cast a value to this type.
        
        This method uses the cast_info stored on the class to determine
        which casting strategy to use.
        """
        cast_info = cls._get_cast_info()
        if not cast_info:
            # No cast info - passthrough
            if isinstance(v, cls) or isinstance(v, dict):
                return v
            raise TypeError(f"{cls.__name__}: no cast info available")
        
        field_name = cast_info.get('field', 'value')
        
        if cast_info.get('fn'):
            return _cast_with_fn(cls, v, field_name, cast_info['fn'])
        elif cast_info.get('expr'):
            return _cast_with_expr(cls, v, field_name, cast_info['expr'])
        else:
            return _cast_value_generic(cls, v, field_name, cast_info.get('scalars'))




