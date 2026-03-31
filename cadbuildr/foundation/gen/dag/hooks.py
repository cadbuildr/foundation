"""Hook/plugin system for custom processing during DAG traversal."""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class TraversalContext:
    """Context object passed to hooks during DAG traversal."""
    memo: Dict[str, Any]
    type_registry: Dict[str, int]
    valid_types: set
    current_path: List[str] = field(default_factory=list)
    is_first_encounter: bool = False
    node_hash: Optional[str] = None
    field_name: Optional[str] = None  # For field-level hooks
    expanded_obj: Optional[Any] = None  # For after_expand hook


class HookRegistry:
    """Registry for managing hooks during DAG traversal."""
    
    def __init__(self):
        self._hooks: Dict[str, Dict[str, List[Callable]]] = {}
        self._first_encountered: set = set()
    
    def register(self, hook_type: str, type_name: str | List[str], callback: Callable) -> None:
        """
        Register a hook for a specific type or types.
        
        Args:
            hook_type: Type of hook ('on_encounter', 'on_first_encounter', etc.)
            type_name: Type name(s) to match
            callback: Function to call (obj, context) -> None
        """
        if hook_type not in self._hooks:
            self._hooks[hook_type] = {}
        
        type_names = [type_name] if isinstance(type_name, str) else type_name
        for name in type_names:
            if name not in self._hooks[hook_type]:
                self._hooks[hook_type][name] = []
            self._hooks[hook_type][name].append(callback)
    
    def get_hooks(self, hook_type: str, type_name: str) -> List[Callable]:
        """Get all hooks for a specific hook type and type name."""
        if hook_type not in self._hooks:
            return []
        return self._hooks[hook_type].get(type_name, [])
    
    def run_hooks(self, hook_type: str, obj: Any, context: TraversalContext) -> None:
        """Execute all hooks for a specific hook type and object type."""
        type_name = obj.__class__.__name__
        hooks = self.get_hooks(hook_type, type_name)
        
        for hook in hooks:
            try:
                hook(obj, context)
            except Exception as e:
                # Don't let hook errors break DAG conversion
                print(f"Warning: Hook {hook_type} for {type_name} raised error: {e}")
    
    def mark_encountered(self, node_hash: str) -> bool:
        """Mark a node as encountered and return True if it's the first time."""
        if node_hash in self._first_encountered:
            return False
        self._first_encountered.add(node_hash)
        return True
    
    def clear(self) -> None:
        """Clear all hooks and encountered nodes (for testing)."""
        self._hooks.clear()
        self._first_encountered.clear()


# Global hook registry (can be overridden by passing HookRegistry to conversion)
_global_registry = HookRegistry()


def register_hook(hook_type: str, type_name: str | List[str], callback: Optional[Callable] = None):
    """
    Register a hook. Can be used as decorator or function.
    
    Examples:
        @register_hook("on_encounter", "MyType")
        def my_hook(obj, context):
            ...
        
        register_hook("on_encounter", "MyType", my_hook)
    """
    if callback is None:
        # Used as decorator
        def decorator(func: Callable) -> Callable:
            _global_registry.register(hook_type, type_name, func)
            return func
        return decorator
    else:
        # Used as function
        _global_registry.register(hook_type, type_name, callback)


def get_hooks(hook_type: str, type_name: str) -> List[Callable]:
    """Get hooks for a type (from global registry)."""
    return _global_registry.get_hooks(hook_type, type_name)


def run_hooks(hook_type: str, obj: Any, context: TraversalContext, registry: Optional[HookRegistry] = None) -> None:
    """Execute hooks (uses provided registry or global)."""
    reg = registry if registry is not None else _global_registry
    reg.run_hooks(hook_type, obj, context)


def clear_hooks() -> None:
    """Clear all hooks (for testing)."""
    _global_registry.clear()

