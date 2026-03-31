"""Computable mixin for types with @compute fields."""

from typing import Any

from .helpers import _eval_expr, run_compute


class Computable:
    """Mixin for types with @compute fields."""
    
    def __getattribute__(self, name: str) -> Any:
        """
        Override __getattribute__ to lazily compute fields when they're None.
        This is called for ALL attribute access, so we can intercept None values.
        """
        # Get the value using the parent class's __getattribute__ to avoid infinite recursion
        try:
            value = super().__getattribute__(name)
        except AttributeError:
            # Attribute doesn't exist, let Pydantic handle it
            raise
        
        # If value is None and this is a computed field, compute it
        if value is None and not name.startswith('_'):
            try:
                model_fields = super().__getattribute__('__class__').model_fields
                if name in model_fields:
                    fld = model_fields[name]
                    meta = fld.json_schema_extra or {}
                    
                    # If field has @compute metadata, compute it now
                    if 'compute' in meta:
                        # Check if we're already computing this field (prevent infinite recursion)
                        computing_key = f'_computing_{name}'
                        try:
                            is_computing = super().__getattribute__(computing_key)
                        except AttributeError:
                            is_computing = False
                        
                        if not is_computing:
                            # Mark as computing
                            object.__setattr__(self, computing_key, True)
                            try:
                                computed_value = self.compute(name)
                                # Cache the computed value
                                object.__setattr__(self, name, computed_value)
                                return computed_value
                            finally:
                                # Unmark as computing
                                object.__setattr__(self, computing_key, False)
            except (AttributeError, ValueError, KeyError):
                # Not a model field or computation failed, return None
                pass
        
        return value
    
    def compute(self, field_name: str) -> Any:
        """Compute value for field with @compute directive."""
        if not hasattr(self.__class__, "model_fields"):
            raise TypeError(f"{self.__class__.__name__} is not a Pydantic model, cannot use Computable.")

        fld = self.__class__.model_fields.get(field_name)
        if not fld:
            raise ValueError(f"Field '{field_name}' not found in model {self.__class__.__name__}.")

        meta = fld.json_schema_extra or {}
        
        # Check for @compute directive first
        compute_meta = meta.get("compute")
        if compute_meta and isinstance(compute_meta, dict):
            # expr support
            if "expr" in compute_meta:
                return _eval_expr(self, compute_meta["expr"])

            # Legacy fn path
            fn_name = compute_meta.get("fn")
            if not fn_name:
                raise ValueError(f"Compute metadata for '{field_name}' is missing 'fn'.")
            return run_compute(self, field_name, compute_meta)
        
        # Check for @default directive
        default_meta = meta.get("default")
        if default_meta and isinstance(default_meta, dict):
            expr = default_meta.get("expr")
            if expr:
                return _eval_expr(None, expr)
        
        raise ValueError(
            f"Field '{field_name}' in model {self.__class__.__name__} has no valid @compute or @default metadata."
        )




