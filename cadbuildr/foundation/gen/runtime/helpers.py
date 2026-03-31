"""Runtime helpers for GraphQL codegen - registration functions and expression evaluation."""

import ast
import json
import re
import math
from itertools import chain
from typing import Any, Callable, Dict, Iterable, Optional, Type

# Global registries for compute, expand, method, and cast functions
_COMPUTE: Dict[str, Callable[[Any, str, dict], Any]] = {}
_EXPAND_CUSTOM: Dict[str, Callable[[Any, dict], Any]] = {}
_METHOD: Dict[str, Callable[[Any], Any]] = {}
_CAST_CUSTOM: Dict[str, Callable[[Any], Any]] = {}

# Type registry for expression evaluation (breaks circular dependency)
_TYPE_REGISTRY: Dict[str, Type] = {}

_EXPR_RE = re.compile(r"^(?P<attr>\w+)(\[is (?P<type>\w+)\])?$")


def register_type(name: str, type_class: Type) -> None:
    """Register a type in the type registry for expression evaluation.
    
    This breaks the circular dependency: models import runtime, models register themselves,
    runtime uses registry (no import needed).
    """
    _TYPE_REGISTRY[name] = type_class


def _eval_expr(root, expr: str, local_vars: Optional[Dict[str, Any]] = None):
    """
    Very small path/-filter evaluator.
      • Dot-separated steps (`a.b.c`)
      • Optional filter   (`parts[is Fruit]`)
    Returns either a single value or a list, depending on the path.
    """
    # Handle simple scalar values and literals (for @default)
    try:
        # Handle empty list
        if expr == '[]':
            return []
        # Handle empty dict
        if expr == '{}':
            return {}
        # Try to parse as a simple number or string literal
        if expr.replace('.', '').replace('-', '').isdigit() or expr.replace('.', '').replace('-', '').replace('e', '').replace('E', '').replace('+', '').isdigit():
            return float(expr)
        elif expr.startswith('"') and expr.endswith('"'):
            return expr[1:-1]  # Remove quotes
        elif expr.startswith("'") and expr.endswith("'"):
            return expr[1:-1]  # Remove quotes
    except:
        pass
    
    # Handle complex expressions (function calls, math operations, array indexing, list comprehensions, etc.)
    # Use AST parsing for more robust detection
    has_path_filter = '[is ' in expr or '[isinstance(' in expr
    
    # Try to parse as Python AST to detect complexity
    has_list_comprehension = False
    has_complex_ops = False
    starts_with_type = False
    
    try:
        tree = ast.parse(expr, mode='eval')
        
        # Check for complex operations by walking AST
        for node in ast.walk(tree):
            # List comprehensions
            if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                has_list_comprehension = True
                break
            
            # Function calls (except attribute access)
            if isinstance(node, ast.Call) and not isinstance(node.func, ast.Attribute):
                has_complex_ops = True
                break
            
            # Binary operations (arithmetic, comparisons)
            if isinstance(node, ast.BinOp):
                has_complex_ops = True
                break
            
            # Comparisons
            if isinstance(node, ast.Compare):
                has_complex_ops = True
                break
            
            # If expressions (ternary)
            if isinstance(node, ast.IfExp):
                has_complex_ops = True
                break
            
            # Subscript (indexing)
            if isinstance(node, ast.Subscript):
                has_complex_ops = True
                break
        
        # Check if starts with type (Name node with uppercase first letter, or Attribute starting with uppercase)
        if isinstance(tree.body, ast.Name) and tree.body.id and tree.body.id[0].isupper():
            starts_with_type = True
        elif isinstance(tree.body, ast.Attribute):
            # Check if the attribute chain starts with an uppercase name (e.g., Size.MEDIUM)
            node = tree.body
            while isinstance(node, ast.Attribute):
                node = node.value
            if isinstance(node, ast.Name) and node.id and node.id[0].isupper():
                starts_with_type = True
        elif isinstance(tree.body, ast.Call) and isinstance(tree.body.func, ast.Name):
            if tree.body.func.id and tree.body.func.id[0].isupper():
                starts_with_type = True
        elif isinstance(tree.body, ast.Call) and isinstance(tree.body.func, ast.Attribute):
            # Check if the call is on a type (e.g., IngredientAmount(...))
            node = tree.body.func
            while isinstance(node, ast.Attribute):
                node = node.value
            if isinstance(node, ast.Name) and node.id and node.id[0].isupper():
                starts_with_type = True
    except SyntaxError:
        # If not valid Python syntax, it might be a path expression
        # Fall back to simple heuristics for path filters
        if has_path_filter:
            # Path expression with filter, use path evaluation
            pass
        else:
            # Unknown syntax, try eval anyway
            has_complex_ops = True
    
    if has_list_comprehension or (has_complex_ops and not has_path_filter) or starts_with_type:
        # This looks like a function call or complex expression, use eval
        try:
            # Create a safe namespace with commonly needed modules and the current object
            namespace = {'math': math}
            
            # Add all registered types to the namespace (from type registry)
            namespace.update(_TYPE_REGISTRY)
            
            # Also try to import types from models module (for cases where types aren't registered yet)
            try:
                from importlib import import_module
                import inspect
                
                models_module_name = None
                
                # Get the module of the root object (if available)
                if root and hasattr(root, '__class__') and hasattr(root.__class__, '__module__'):
                    module_name = root.__class__.__module__
                    # Try to import models module: gen.models.smoothie -> gen.models
                    models_module_name = module_name.rsplit('.', 1)[0] if '.' in module_name else module_name
                elif root is None or (isinstance(root, dict) and not root):
                    # When root is None (static methods) or {} (default expressions),
                    # infer models module from runtime module location
                    # Runtime module: {package}.gen.runtime.helpers -> Models module: {package}.gen.models
                        try:
                            # Use __name__ from this function's module (helpers.py)
                            # This will be something like 'smoothies.gen.runtime.helpers'
                            current_module = __name__
                            if current_module and '.gen.runtime.helpers' in current_module:
                                # Replace .gen.runtime.helpers with .gen.models
                                models_module_name = current_module.replace('.gen.runtime.helpers', '.gen.models')
                            elif current_module and '.gen.runtime' in current_module:
                                # Replace .gen.runtime with .gen.models (handles .gen.runtime.something)
                                models_module_name = current_module.replace('.gen.runtime', '.gen.models').rsplit('.', 1)[0]
                            elif current_module and 'runtime' in current_module:
                                # Fallback: try to replace 'runtime' with 'models' in module path
                                models_module_name = current_module.replace('runtime', 'models').rsplit('.', 1)[0]
                        except Exception:
                            pass
                
                if models_module_name:
                    try:
                        models_mod = import_module(models_module_name)
                        # Add all uppercase names (likely types) from models module
                        for name in dir(models_mod):
                            if name[0].isupper() and not name.startswith('_'):
                                if name not in namespace:
                                    namespace[name] = getattr(models_mod, name)
                    except (ImportError, AttributeError):
                        pass
            except Exception:
                pass
            
            if isinstance(root, dict):
                namespace.update(root)
            elif root is not None:
                # Add the current object and its attributes to the namespace
                namespace.update(vars(root) if hasattr(root, '__dict__') else {})
                # For pydantic models, also include the field values
                if hasattr(root, '__dict__'):
                    for key, value in root.__dict__.items():
                        namespace[key] = value
            # If root is None (static methods), just use registry namespace + local_vars
            
            # Add method parameters to evaluation context
            if local_vars:
                # Filter out 'self' which is already in namespace via root
                params = {k: v for k, v in local_vars.items() if k != 'self'}
                namespace.update(params)
            
            return eval(expr, namespace, namespace)
        except NameError as e:
            # If a type is still not found, try to import it dynamically
            missing_name = str(e).split("'")[1] if "'" in str(e) else None
            if missing_name and missing_name[0].isupper():  # Likely a type name
                try:
                    from importlib import import_module
                    import inspect
                    
                    models_module_name = None
                    
                    # Try to import from models module
                    if root and hasattr(root, '__class__') and hasattr(root.__class__, '__module__'):
                        module_name = root.__class__.__module__
                        models_module_name = module_name.rsplit('.', 1)[0] if '.' in module_name else module_name
                    elif root is None or (isinstance(root, dict) and not root):
                        # When root is None or {}, infer models module from runtime module location
                        try:
                            # Use __module__ from this function's module (helpers.py)
                            current_module = __name__
                            if current_module and '.gen.runtime' in current_module:
                                models_module_name = current_module.replace('.gen.runtime', '.gen.models')
                            elif current_module and 'runtime' in current_module:
                                models_module_name = current_module.replace('runtime', 'models')
                        except Exception:
                            pass
                    
                    if models_module_name:
                        try:
                            models_mod = import_module(models_module_name)
                            if hasattr(models_mod, missing_name):
                                namespace[missing_name] = getattr(models_mod, missing_name)
                                return eval(expr, namespace, namespace)
                        except (ImportError, AttributeError):
                            pass
                except Exception:
                    pass
            # If eval fails for static methods (root is None), re-raise since path evaluation won't work
            if root is None:
                raise ValueError(f"Failed to evaluate static method expression '{expr}': {e}")
            # For instance methods with complex expressions, also re-raise - don't fall back to path evaluation
            if has_list_comprehension or has_complex_ops:
                raise ValueError(f"Failed to evaluate expression '{expr}': {e}")
            # Only fall back to path evaluation for simple path-like expressions
            pass
        except Exception as e:
            # If eval fails for static methods (root is None), re-raise since path evaluation won't work
            if root is None:
                raise ValueError(f"Failed to evaluate static method expression '{expr}': {e}")
            # For instance methods with complex expressions, also re-raise - don't fall back to path evaluation
            if has_list_comprehension or has_complex_ops:
                raise ValueError(f"Failed to evaluate expression '{expr}': {e}")
            # Only fall back to path evaluation for simple path-like expressions
            pass
    
    # Original path evaluation logic (only for instance methods with a root object)
    if root is None:
        raise ValueError(f"Cannot use path evaluation on None root for expression: {expr}")
    items: Iterable[Any] = [root]

    for step in expr.split("."):
        m = _EXPR_RE.match(step)
        if not m:
            raise ValueError(f"Invalid expr token: {step!r}")

        attr, want_type = m["attr"], m["type"]
        next_items = []
        for it in items:
            value = getattr(it, attr)
            # NEW - lazy-fill a field whose value is None and carries @default metadata
            if value is None:
                try:
                    value = it.compute(attr)   # will succeed for @default/@compute
                except (ValueError, AttributeError):
                    pass
            seq = value if isinstance(value, list) else [value]

            if want_type:
                # Enhanced filtering: check if the object itself or its common nested properties match the type
                filtered_seq = []
                for x in seq:
                    if x.__class__.__name__ == want_type:
                        # Direct type match
                        filtered_seq.append(x)
                    elif hasattr(x, 'ingredient') and x.ingredient.__class__.__name__ == want_type:
                        # Check if ingredient property matches the type (for IngredientAmount -> Fruit filtering)
                        filtered_seq.append(x)
                    # Could add more nested property checks here if needed
                seq = filtered_seq

            next_items.extend(seq)
        items = next_items

    # Flatten: if every element is a primitive, return list-or-scalar
    if not items:
        return []
    if len(items) == 1:
        return items[0]
    return list(items)


# Registration functions
def register_compute_fn(name: str):
    def _wrap(fn):
        _COMPUTE[name] = fn
        return fn
    return _wrap


def register_method_fn(name: str):
    def _wrap(fn):
        _METHOD[name] = fn
        return fn
    return _wrap


def run_method(inst, fn_name: str, local_vars: Optional[Dict[str, Any]] = None):
    """Execute a registered method function with optional parameters."""
    if fn_name not in _METHOD:
        raise ValueError(f"Method fn '{fn_name}' not registered")
    
    method_fn = _METHOD[fn_name]
    
    if local_vars is None:
        # Zero-parameter method (backward compatible)
        return method_fn(inst)
    
    # Parametrized method - pass arguments
    import inspect
    sig = inspect.signature(method_fn)
    param_names = [p for p in sig.parameters.keys() if p != 'inst']
    
    # Extract only the parameters the function expects
    kwargs = {k: v for k, v in local_vars.items() if k in param_names}
    return method_fn(inst, **kwargs)


def register_expand_fn(name: str):
    def _wrap(fn):
        _EXPAND_CUSTOM[name] = fn
        return fn
    return _wrap


def run_compute(inst, field_name: str, meta: dict):
    fn_name = meta.get("fn")
    if not fn_name or fn_name not in _COMPUTE:
        raise ValueError(f"Compute function '{fn_name}' not registered for field '{field_name}'.")
    return _COMPUTE[fn_name](inst, field_name, meta)


def register_cast_fn(name: str):
    """Register a custom casting function for @cast directive."""
    def _wrap(fn):
        _CAST_CUSTOM[name] = fn
        return fn
    return _wrap

