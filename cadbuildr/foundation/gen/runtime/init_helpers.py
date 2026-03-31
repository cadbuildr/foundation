"""Init helper functions for @cast and @ordered directive support."""

from typing import Any, Dict, List, Optional, Tuple


def _handle_ordered_args(
    args: Tuple[Any, ...],
    kwargs: Dict[str, Any],
    field_order: List[str],
    list_fields: List[str],
    all_field_names: List[str],
) -> Dict[str, Any]:
    """Handle @ordered directive positional arguments.
    
    Args:
        args: Positional arguments
        kwargs: Keyword arguments (will be modified)
        field_order: Ordered list of field names
        list_fields: List of field names that are List types
        all_field_names: All field names in the model
        
    Returns:
        Updated kwargs dictionary
    """
    if len(args) > 1:
        # Map positional args to field names in the specified order
        for i, arg in enumerate(args):
            if i < len(field_order):
                field_name = field_order[i]
                # Auto-wrap single items into lists for List fields
                if field_name in list_fields and not isinstance(arg, list):
                    kwargs[field_name] = [arg]
                else:
                    kwargs[field_name] = arg
            elif i - len(field_order) < len(all_field_names) - len(field_order):
                # Map extra args to remaining fields not in ordered list
                remaining_fields = [f for f in all_field_names if f not in field_order]
                kwargs[remaining_fields[i - len(field_order)]] = arg
    elif len(args) == 1:
        # Map the single positional arg to the first ordered field
        if field_order:
            field_name = field_order[0]
            # Auto-wrap single items into lists for List fields
            if field_name in list_fields and not isinstance(args[0], list):
                kwargs[field_name] = [args[0]]
            else:
                kwargs[field_name] = args[0]
    
    return kwargs


def _handle_cast_arg(cls, arg: Any, cast_info: Dict[str, Any]) -> Dict[str, Any]:
    """Handle @cast directive for single positional argument.
    
    Args:
        cls: The class being instantiated
        arg: The positional argument to cast
        cast_info: Dictionary with cast information (field name, etc.)
        
    Returns:
        Dictionary ready for super().__init__(**result)
    """
    try:
        casted = cls._cast(arg)
    except TypeError as e:
        # tests expect "cannot cast" in the message
        raise
    
    # Handle the result: if it's already an instance, copy its data
    if isinstance(casted, cls):
        # Copy the fields from the existing instance
        return casted.model_dump()
    elif isinstance(casted, dict):
        # Use the dict directly
        return casted
    else:
        # `_cast` returned a scalar, wrap it in the field
        return {cast_info['field']: casted}


def _init_with_cast(
    cls,
    args: Tuple[Any, ...],
    kwargs: Dict[str, Any],
    cast_info: Optional[Dict[str, Any]] = None,
    field_order: Optional[List[str]] = None,
    list_fields: Optional[List[str]] = None,
) -> Tuple[bool, Dict[str, Any]]:
    """Generic __init__ with cast/ordered support.
    
    This function handles the complex logic for positional arguments with
    @cast and @ordered directives. Returns (use_normal_init, processed_kwargs).
    
    Args:
        cls: The class being instantiated (use self.__class__)
        args: Positional arguments
        kwargs: Keyword arguments
        cast_info: Optional cast information dict with 'field' key
        field_order: Optional ordered list of field names for @ordered directive
        list_fields: Optional list of field names that are List types
        
    Returns:
        Tuple of (use_normal_init: bool, processed_kwargs: dict)
        If use_normal_init is True, call super().__init__(*args, **kwargs)
        Otherwise, call super().__init__(**processed_kwargs)
    """
    result_kwargs = dict(kwargs)
    
    if field_order:
        # Handle @ordered directive
        all_field_names = list(cls.model_fields.keys())
        list_fields = list_fields or []
        
        if len(args) > 1:
            # Multiple positional args - map to ordered fields
            result_kwargs = _handle_ordered_args(
                args, result_kwargs, field_order, list_fields, all_field_names
            )
            return (False, result_kwargs)
        elif len(args) == 1:
            # Single positional arg with @ordered
            kwargs_was_empty = len(result_kwargs) == 0
            result_kwargs = _handle_ordered_args(
                args, result_kwargs, field_order, list_fields, all_field_names
            )
            
            # Handle @cast directive if kwargs was empty before processing and cast is available
            if kwargs_was_empty and len(result_kwargs) == 0 and cast_info and hasattr(cls, '_cast'):
                result_kwargs = _handle_cast_arg(cls, args[0], cast_info)
                return (False, result_kwargs)
            elif kwargs_was_empty and len(result_kwargs) == 0:
                # Only @ordered directive, no casting - fall back to normal constructor
                return (True, kwargs)
            else:
                # Mixed positional and keyword args for ordered type, or arg was mapped to field
                return (False, result_kwargs)
        else:
            # zero or keyword args – default behaviour
            return (True, kwargs)
    elif cast_info:
        # Handle @cast directive only (no @ordered)
        if args and not kwargs:
            result_kwargs = _handle_cast_arg(cls, args[0], cast_info)
            return (False, result_kwargs)
        else:
            # zero or keyword args – default behaviour
            return (True, kwargs)
    else:
        # No directives - normal constructor
        return (True, kwargs)

