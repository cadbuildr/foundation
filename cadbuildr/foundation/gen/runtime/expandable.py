"""Expandable mixin for types with @expand directive."""

import json
from typing import Any, Dict, get_args, get_origin, Union
from pydantic import BaseModel

from .helpers import _EXPAND_CUSTOM, _eval_expr


class Expandable:
    """Mixin for types with @expand directive."""
    def expand(self) -> Any:
        """Expand this node into primitive components."""
        if not hasattr(self.__class__, "model_fields"):
             raise TypeError(f"{self.__class__.__name__} is not a Pydantic model, cannot use Expandable.")

        expansion_data_source = getattr(self, "__expansion__", None)

        if expansion_data_source is None:
            if "result" in self.__class__.model_fields:
                result_field_info = self.__class__.model_fields["result"]
                meta_on_result_field = result_field_info.json_schema_extra or {}
                expand_meta_on_field = meta_on_result_field.get("expand")
                if expand_meta_on_field and isinstance(expand_meta_on_field, dict) and "into" in expand_meta_on_field:
                    into_value = expand_meta_on_field["into"]
                    if isinstance(into_value, dict):
                        # 'into' is already a dict - use directly
                        expansion_data_source = into_value
                    else:
                        # 'into' is still a string - parse it (backward compatibility)
                        try:
                            expansion_data_source = json.loads(into_value)
                        except json.JSONDecodeError as e:
                            raise ValueError(
                                f"Failed to parse 'into' JSON for field 'result' in {self.__class__.__name__}: {e}\n"
                                f"Content: {into_value[:100] if isinstance(into_value, str) else str(into_value)[:100]}..."
                            )
                else:
                     raise ValueError(
                        f"Type {self.__class__.__name__} is Expandable but has no __expansion__ attribute "
                        f"and its 'result' field lacks valid @expand metadata."
                    )
            else:
                 raise ValueError(
                    f"Type {self.__class__.__name__} is Expandable but has no __expansion__ attribute or 'result' field to source expansion data."
                )

        if not isinstance(expansion_data_source, dict):
            raise ValueError(
                f"Resolved expansion data for {self.__class__.__name__} must be a dictionary. Got: {type(expansion_data_source)}"
            )

        return run_expand(self, expansion_data_source)


def run_expand(inst, expansion_dict_resolved: dict):
    if "fn" in expansion_dict_resolved:
        fn_name = expansion_dict_resolved["fn"]
        if fn_name not in _EXPAND_CUSTOM:
            raise ValueError(f"Custom expand function '{fn_name}' not registered.")
        return _EXPAND_CUSTOM[fn_name](inst, expansion_dict_resolved)

    # For default expansion, we need to detect the target class
    # Look for the 'result' field to get its type annotation
    if hasattr(inst.__class__, 'model_fields') and 'result' in inst.__class__.model_fields:
        from typing import get_type_hints
        from importlib import import_module
        try:
            # Get the module namespace to resolve forward references
            mod = import_module(inst.__class__.__module__)
            ns = vars(mod)  # globalns/locals for hints
            
            # Also import from models module to get all types (needed when using TYPE_CHECKING imports)
            try:
                # Try to import models module: gen.models.smoothie_from_fruit_and_addon -> gen.models
                models_module_name = inst.__class__.__module__.rsplit('.', 1)[0]
                models_mod = import_module(models_module_name)
                # Update namespace with all types from models module
                ns.update({k: v for k, v in vars(models_mod).items() if not k.startswith('_')})
            except (ImportError, ValueError):
                pass  # Fallback to just using the current module
            
            type_hints = get_type_hints(inst.__class__, ns, ns)
            target_cls = type_hints.get('result')
            if target_cls:
                # Unwrap Optional[X] to X (Optional[X] is Union[X, None])
                origin = get_origin(target_cls)
                if origin is Union:
                    args = get_args(target_cls)
                    # Filter out NoneType to get the actual type
                    non_none_args = [arg for arg in args if arg is not type(None)]
                    if len(non_none_args) == 1:
                        target_cls = non_none_args[0]
                
                return _default_expand(inst, expansion_dict_resolved, target_cls=target_cls)
        except (ImportError, NameError, AttributeError) as e:
            # Fallback if type hints can't be resolved
            pass

    # Fallback: if we can't determine target class, raise an error
    raise ValueError(
        f"Cannot determine target class for expansion of {inst.__class__.__name__}. "
        f"Make sure the expanded field has a proper type annotation."
    )


def _default_expand(instance: Any, expansion_template: Dict[str, Any], *, target_cls) -> Any:
    """
    Generic Pydantic model-based expansion engine.
    Replaces placeholders like "$field_name" with instance attribute values.
    Recursively builds Pydantic model instances instead of raw dictionaries.

    Args:
        instance: The model instance from which to pull placeholder values
        expansion_template: The dictionary template guiding the expansion
        target_cls: The Pydantic model class to instantiate

    Returns:
        Fully instantiated Pydantic model of type target_cls
    """
    def _substitute_value(value, field_annotation):
        """Recursively substitute values based on type annotation."""
        # 1. Placeholder substitution
        if isinstance(value, str) and value.startswith("$"):
            attr_name = value[1:]  # Remove "$" prefix
            # Try to get attribute - prioritize exact match, then model fields only
            attr_value = None
            if hasattr(instance, attr_name):
                attr_value = getattr(instance, attr_name)
            else:
                # Try case-insensitive match in model_fields only (not all dir() attributes)
                # This prevents matching enum classes like Size instead of field size
                if hasattr(instance.__class__, 'model_fields'):
                    for field_name in instance.__class__.model_fields.keys():
                        if field_name.lower() == attr_name.lower():
                            attr_value = getattr(instance, field_name)
                            break
            
            # If the value is None and the field is computable, compute it first
            if attr_value is None and hasattr(instance, 'compute'):
                try:
                    attr_value = instance.compute(attr_name)
                except (ValueError, AttributeError) as e:
                    # Let the error propagate with context
                    raise ValueError(f"Failed to compute placeholder {value!r} on {instance.__class__.__name__}: {e}") from e
            
            if attr_value is None:
                raise ValueError(f"Placeholder {value!r} (field '{attr_name}') not found on {instance.__class__.__name__}")
            
            return attr_value

        # 2. Recurse based on annotation
        origin = get_origin(field_annotation) or field_annotation

        # Handle List types
        if isinstance(value, list) and origin is list:
            args = get_args(field_annotation)
            if args:
                elem_type = args[0]
                return [_substitute_value(v, elem_type) for v in value]
            else:
                return value

        # Handle Union types (including discriminated unions with __typename)
        if isinstance(value, dict) and origin is Union:
            args = get_args(field_annotation)
            
            # If dict has __typename, use it to pick the right type from Union
            if "__typename" in value:
                typename = value["__typename"]
                for arg in args:
                    if hasattr(arg, '__name__') and arg.__name__ == typename:
                        return _build_model(value, arg)
                raise ValueError(f"No type matching __typename='{typename}' found in Union {field_annotation}")
            
            # No __typename - try each union member to see which one validates
            for arg in args:
                if arg is type(None):  # Skip NoneType
                    continue
                try:
                    return _build_model(value, arg)
                except Exception:
                    continue  # Try next type
            
            # None of the union members worked
            raise ValueError(f"Could not match {value} to any type in Union {field_annotation}")

        # Handle nested Pydantic models
        if isinstance(value, dict) and isinstance(origin, type) and issubclass(origin, BaseModel):
            return _build_model(value, origin)

        # Primitive value - return as-is
        return value

    def _build_model(src_dict: dict, model_cls):
        """Build a Pydantic model from a dictionary using field annotations."""
        if not hasattr(model_cls, 'model_fields'):
            raise ValueError(f"{model_cls.__name__} is not a Pydantic model")

        data = {}
        
        for field_name, field_info in model_cls.model_fields.items():
            if field_name in src_dict:
                field_annotation = field_info.annotation
                data[field_name] = _substitute_value(src_dict[field_name], field_annotation)
            # If field is missing and not computed, let Pydantic handle the error
            # If field is missing and computed, it will use default=None and be computed later

        # Create instance with available fields (computed fields will be None by default)
        try:
            instance = model_cls(**data)
        except Exception as e:
            raise ValueError(f"@expand could not build {model_cls.__name__}: {e}") from e
        
        # Now compute any computed fields that are None
        for field_name, field_info in model_cls.model_fields.items():
            if getattr(instance, field_name, None) is None:
                meta = field_info.json_schema_extra or {}
                compute_meta = meta.get("compute")
                if compute_meta and isinstance(compute_meta, dict):
                    try:
                        computed_value = instance.compute(field_name)
                        setattr(instance, field_name, computed_value)
                    except Exception as e:
                        raise ValueError(
                            f"Failed to compute field '{field_name}' for {model_cls.__name__}. "
                            f"Make sure the compute function '{compute_meta.get('fn')}' is registered."
                        ) from e
        
        return instance

    return _build_model(expansion_template, target_cls)

