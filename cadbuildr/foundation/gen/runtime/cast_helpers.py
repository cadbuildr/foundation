"""Cast helper functions for @cast directive support."""

from typing import Any, Dict, List, Optional
from .helpers import _CAST_CUSTOM


def _cast_value_generic(cls, v: Any, field_name: str, scalars: Optional[List[str]] = None) -> Dict[str, Any]:
    """Generic casting logic for auto-cast types based on field type.
    
    Args:
        cls: The class being cast to
        v: The value to cast
        field_name: Name of the field to cast to
        scalars: Optional list of scalar type names for error messages
        
    Returns:
        Dictionary with field_name as key and cast value
    """
    # 0️⃣ passthroughs
    if isinstance(v, cls) or isinstance(v, dict):
        return v
    
    # 3️⃣ fallback: auto-cast based on field type
    try:
        # Detect the field type and cast appropriately
        field_annotations = cls.model_fields
        if field_name in field_annotations:
            field_info = field_annotations[field_name]
            # Get the annotation (type) from the field info
            field_annotation = field_info.annotation
            
            # Handle typing wrappers like Union, Optional, etc.
            import typing
            if hasattr(typing, 'get_origin') and typing.get_origin(field_annotation):
                # For Union types, get the first non-None type
                args = typing.get_args(field_annotation)
                for arg in args:
                    if arg != type(None):
                        field_annotation = arg
                        break
            
            # Cast based on the field type
            if field_annotation == str:
                return {field_name: str(v)}
            elif field_annotation == int:
                return {field_name: int(v)}
            elif field_annotation == bool:
                return {field_name: bool(v)}
            elif field_annotation == float:
                return {field_name: float(v)}
        
        # Default to float if we can't determine the type
        return {field_name: float(v)}
    except (TypeError, ValueError) as e:
        scalar_str = f" from {' / '.join(scalars)}" if scalars else ""
        raise TypeError(
            f"{cls.__name__}: cannot cast {v!r}{scalar_str}"
        ) from e


def _cast_with_expr(cls, v: Any, field_name: str, expr: str) -> Dict[str, Any]:
    """Expression-based casting.
    
    Args:
        cls: The class being cast to
        v: The value to cast
        field_name: Name of the field to cast to
        expr: Python expression to evaluate for casting
        
    Returns:
        Dictionary with field_name as key and cast value
    """
    # 0️⃣ passthroughs
    if isinstance(v, cls) or isinstance(v, dict):
        return v
    
    # 2️⃣ inline expression
    _v = v  # keep original name available in eval
    try:
        import builtins
        namespace = {'v': v, '_v': _v, '__builtins__': builtins.__dict__}
        result = eval(expr, namespace)
        # If result is a scalar, wrap it in the field
        if not isinstance(result, dict):
            return {field_name: result}
        return result
    except Exception as e:
        raise TypeError(f"{cls.__name__}: cannot cast {_v!r}") from e


def _cast_with_fn(cls, v: Any, field_name: str, fn_name: str) -> Dict[str, Any]:
    """Function-based casting using registered cast functions.
    
    Args:
        cls: The class being cast to
        v: The value to cast
        field_name: Name of the field to cast to
        fn_name: Name of the registered cast function
        
    Returns:
        Dictionary with field_name as key and cast value
    """
    # 0️⃣ passthroughs
    if isinstance(v, cls) or isinstance(v, dict):
        return v
    
    # 1️⃣ runtime function wins
    _fn = _CAST_CUSTOM.get(fn_name)
    if _fn:
        result = _fn(v)
        # If result is a scalar, wrap it in the field
        if not isinstance(result, dict):
            return {field_name: result}
        return result
    
    # Fall back if function not registered: just wrap the value
    try:
        return {field_name: str(v)}
    except Exception as e:
        raise TypeError(f"{cls.__name__}: cannot cast {v!r}") from e

