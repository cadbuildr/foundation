"""Core Pydantic model to DAG node conversion."""

from typing import Any, Dict, Optional, Set

from pydantic import BaseModel

from .hash import compute_hash
from .hooks import HookRegistry, TraversalContext, run_hooks


def _get_type_id(type_name: str, type_registry: Dict[str, int]) -> int:
    """Get type ID from registry, adding it if not present."""
    if type_name not in type_registry:
        # Add new type to registry with next available ID
        max_id = max(type_registry.values()) if type_registry else -1
        type_registry[type_name] = max_id + 1
    return type_registry[type_name]


def _expand_type_if_needed(
    obj: BaseModel,
    type_name: str,
    valid_types: set,
    context: TraversalContext,
    hooks: Optional[HookRegistry]
) -> Optional[BaseModel]:
    """
    Expand a type if it's not in valid_types and has an expand method.
    
    Returns:
        Expanded object if expansion occurred, None otherwise
    """
    if type_name not in valid_types and hasattr(obj, 'expand'):
        expanded = obj.expand()
        if expanded is not None:
            # Run after_expand hook for custom processing (e.g., sketch propagation)
            # Pass both original and expanded objects via context
            if hooks:
                # Store expanded object in context for hooks to access
                context.expanded_obj = expanded
                run_hooks("after_expand", obj, context, hooks)
                expanded = context.expanded_obj  # Hook may have modified it
            return expanded
        raise Exception(f"Failed to expand {type_name} into {expanded}")
    return None


def _compute_field_if_needed(obj: BaseModel, field_name: str) -> Any:
    """Compute a field value if it's None and the object has a compute method."""
    field_value = getattr(obj, field_name)
    if field_value is None and hasattr(obj, 'compute'):
        try:
            field_value = obj.compute(field_name)
            # Update the object with the computed value so it's available for other computations
            setattr(obj, field_name, field_value)
        except (ValueError, AttributeError):
            pass
    return field_value


def _should_skip_field(field_name: str, obj: BaseModel, hooks: Optional[HookRegistry], context: TraversalContext) -> bool:
    """Check if a field should be skipped during processing."""
    if hooks:
        # Check both type-specific and wildcard hooks
        type_name = obj.__class__.__name__
        hooks_to_check = hooks.get_hooks("should_skip_field", type_name) + hooks.get_hooks("should_skip_field", "*")
        for hook in hooks_to_check:
            try:
                if hook(field_name, obj, context):
                    return True
            except Exception:
                pass
    return False


def _process_single_field(
    field_name: str,
    field_value: Any,
    obj: BaseModel,
    type_name: str,
    memo: Dict[str, Any],
    type_registry: Dict[str, int],
    context: TraversalContext,
    hooks: Optional[HookRegistry]
) -> tuple[Optional[Any], Optional[Any]]:
    """
    Process a single field value.
    
    Returns:
        Tuple of (param_value, dep_value). One will be None, the other will have the value.
    """
    # Run before_field hook
    if hooks:
        field_context = TraversalContext(
            memo=context.memo,
            type_registry=context.type_registry,
            valid_types=context.valid_types,
            current_path=context.current_path,
            is_first_encounter=context.is_first_encounter,
            node_hash=context.node_hash,
            field_name=field_name
        )
        run_hooks("before_field", obj, field_context, hooks)
        
        # Check if field should be processed as a special case
        special_hooks = hooks.get_hooks("process_field", f"{type_name}.{field_name}")
        for hook in special_hooks:
            try:
                result = hook(field_name, field_value, obj, field_context)
                if result is not None:
                    return result  # Hook handled the field
            except Exception:
                pass
    
    processing_set = context.processing if hasattr(context, 'processing') else None

    def _convert_nested(value: Any) -> tuple[bool, Any]:
        if isinstance(value, BaseModel):
            return True, pydantic_to_dag(value, memo, type_registry, hooks, processing_set)
        if isinstance(value, list):
            has_dep = False
            out = []
            for item in value:
                item_dep, converted = _convert_nested(item)
                has_dep = has_dep or item_dep
                out.append(converted)
            return has_dep, out
        if isinstance(value, tuple):
            has_dep = False
            out = []
            for item in value:
                item_dep, converted = _convert_nested(item)
                has_dep = has_dep or item_dep
                out.append(converted)
            return has_dep, out
        if isinstance(value, set):
            has_dep = False
            out = []
            for item in value:
                item_dep, converted = _convert_nested(item)
                has_dep = has_dep or item_dep
                out.append(converted)
            return has_dep, out
        if isinstance(value, dict):
            has_dep = False
            out = {}
            for k, item in value.items():
                item_dep, converted = _convert_nested(item)
                has_dep = has_dep or item_dep
                out[k] = converted
            return has_dep, out
        return False, value

    has_dep, converted_value = _convert_nested(field_value)
    if has_dep:
        return None, converted_value
    # Primitive value - store in params
    return converted_value, None


def _process_fields(
    obj: BaseModel,
    memo: Dict[str, Any],
    type_registry: Dict[str, int],
    context: TraversalContext,
    hooks: Optional[HookRegistry]
) -> tuple[dict, dict]:
    """
    Process all fields of an object.
    
    Returns:
        Tuple of (params, deps)
    """
    params = {}
    deps = {}
    
    # Work with actual Pydantic field values, not dumped data
    for field_name in obj.model_fields.keys():
        # Check if field should be skipped
        if _should_skip_field(field_name, obj, hooks, context):
            continue
        
        # Compute field if needed
        field_value = _compute_field_if_needed(obj, field_name)
        
        if field_value is None:
            continue
        
        # Process the field
        param_value, dep_value = _process_single_field(
            field_name, field_value, obj, obj.__class__.__name__, memo, type_registry, context, hooks
        )
        
        if param_value is not None:
            params[field_name] = param_value
        if dep_value is not None:
            deps[field_name] = dep_value
    
    return params, deps


def pydantic_to_dag(
    obj: Any,
    memo: Dict[str, Any],
    type_registry: Optional[Dict[str, int]] = None,
    hooks: Optional[HookRegistry] = None,
    processing: Optional[Set[int]] = None
) -> str:
    """
    Convert a Pydantic model to DAG format recursively.
    Returns the hash ID of the object.
    
    Args:
        obj: Pydantic model instance or primitive value
        memo: Memoization dict to track already processed nodes
        type_registry: Dynamic mapping of type names to integer IDs (defaults to empty dict)
        hooks: Optional hook registry for custom processing
        processing: Set of object IDs currently being processed (for cycle detection)
        
    Returns:
        Hash ID of the object
    """
    if type_registry is None:
        type_registry = {}
    
    valid_types = set(type_registry.keys())
    
    # Handle primitive types
    if not isinstance(obj, BaseModel):
        # For primitives, we don't create nodes, just return the value
        return obj
    
    # Initialize processing set if not provided
    if processing is None:
        processing = set()
    
    # Get object identity for cycle detection
    obj_id = id(obj)
    
    # Early cycle detection: check if this object is currently being processed
    if obj_id in processing:
        # Circular reference detected - this object is already being processed
        # We can't compute the hash yet (needs processed fields), but we can
        # check if it's already in memo by trying a different approach.
        # For now, we'll raise an error with a clear message.
        # In the future, we could return a placeholder hash that gets resolved later.
        type_name = obj.__class__.__name__
        raise ValueError(f"Circular reference detected in DAG conversion for {type_name}. "
                        f"This object (id={obj_id}) is already being processed in the current call stack. "
                        f"This indicates a true cycle in the object graph that cannot be converted to a DAG.")
    
    # Get the type name
    type_name = obj.__class__.__name__
    
    # Create context for hooks
    context = TraversalContext(
        memo=memo,
        type_registry=type_registry,
        valid_types=valid_types,
        current_path=[]
    )
    # Store processing set in context so _process_fields can access it
    context.processing = processing
    
    # Run on_encounter hook (before processing)
    if hooks:
        run_hooks("on_encounter", obj, context, hooks)
    
    # Check for expansion if valid_types is provided and type is not valid
    expanded = _expand_type_if_needed(obj, type_name, valid_types, context, hooks)
    if expanded is not None:
        return pydantic_to_dag(expanded, memo, type_registry, hooks, processing)
    
    # Add object to processing set BEFORE processing fields
    processing.add(obj_id)
    try:
            # Process all fields (may recursively call pydantic_to_dag)
        params, deps = _process_fields(obj, memo, type_registry, context, hooks)
        
        # Get type ID
        type_id = _get_type_id(type_name, type_registry)
        
        # Create node content
        node_content = {
            "type": type_id,
            "params": params,
            "deps": deps
        }
        
        # Run before_node hook
        if hooks:
            run_hooks("before_node", obj, context, hooks)
        
        # Compute hash
        node_hash = compute_hash(node_content)
        context.node_hash = node_hash
        
        # Check if first encounter
        if hooks:
            context.is_first_encounter = hooks.mark_encountered(node_hash)
            if context.is_first_encounter:
                run_hooks("on_first_encounter", obj, context, hooks)
        
        # If already in memo, return the hash
        if node_hash in memo:
            return node_hash
        
        # Run after_node hook
        if hooks:
            run_hooks("after_node", obj, context, hooks)
        
        # Add to memo
        memo[node_hash] = node_content
        
        return node_hash
    finally:
        # Remove object from processing set after processing (even if error occurred)
        processing.discard(obj_id)

