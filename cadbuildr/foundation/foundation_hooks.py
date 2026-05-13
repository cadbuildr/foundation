"""Foundation-specific hooks for DAG processing."""

from typing import Any, Optional

from pydantic import BaseModel

from cadbuildr.foundation.gen.dag.hooks import (
    HookRegistry,
    TraversalContext,
    register_hook,
    _global_registry,
)
from cadbuildr.foundation.mixin.sketch_mixin import SketchElementMixin


def setup_foundation_hooks(registry: Optional[HookRegistry] = None) -> HookRegistry:
    """
    Set up all foundation-specific hooks for DAG processing.

    Args:
        registry: Optional hook registry. If None, uses global registry.

    Returns:
        The hook registry with foundation hooks registered.
    """
    reg = registry if registry is not None else _global_registry

    # Skip 'sketch' field on sketch elements to avoid circular references
    # But keep it for operations like Extrusion which need the sketch reference
    def skip_sketch_field(
        field_name: str, obj: BaseModel, context: TraversalContext
    ) -> bool:
        """Skip sketch field on sketch elements to avoid circular references."""
        if field_name != "sketch":
            return False

        # All SketchElementMixin types self-register into sketch.elements via
        # model_post_init, creating a back-reference that would cause a cycle.
        # Skipping the sketch field on these types breaks the cycle.
        return isinstance(obj, SketchElementMixin)

    reg.register("should_skip_field", "*", skip_sketch_field)

    # Skip 'pf' field on Part to avoid serializing PlaneFactory
    def skip_pf_field(
        field_name: str, obj: BaseModel, context: TraversalContext
    ) -> bool:
        """Skip pf field to avoid serializing PlaneFactory."""
        return field_name == "pf"

    reg.register("should_skip_field", "*", skip_pf_field)

    # Propagate sketch context after expansion (e.g., Square -> Polygon)
    def propagate_sketch_after_expand(
        obj: BaseModel, context: TraversalContext
    ) -> None:
        """Propagate sketch context from original to expanded object."""
        expanded = context.expanded_obj
        if expanded is None:
            return

        # Propagate sketch context if missing in expanded object
        # This is crucial for types like Square -> Polygon where the expansion template
        # might not include the sketch reference, but downstream consumers need it.
        if (
            hasattr(obj, "sketch")
            and hasattr(expanded, "sketch")
            and getattr(expanded, "sketch") is None
        ):
            try:
                setattr(expanded, "sketch", getattr(obj, "sketch"))
            except (AttributeError, ValueError):
                # Some types might have read-only sketch or validation
                pass

    reg.register("after_expand", "*", propagate_sketch_after_expand)

    # Special case: Material.options should be serialized as dict in params
    def process_material_options(
        field_name: str, field_value: Any, obj: BaseModel, context: TraversalContext
    ) -> Optional[tuple[Any, Any]]:
        """Process Material.options as dict in params instead of nested model."""
        if isinstance(field_value, BaseModel):
            diffuse_color = getattr(field_value, "diffuse_color", None)
            if diffuse_color is None:
                return None
            return ({"diffuse_color": diffuse_color}, None)
        return None

    reg.register("process_field", "Material.options", process_material_options)

    # Special case: Extrusion.shape single-item list serialization
    def process_extrusion_shape(
        field_name: str, processed_list: list, obj: BaseModel, context: TraversalContext
    ) -> Optional[tuple[Any, Any]]:
        """For Extrusion.shape, if single-item list, serialize as single value instead of list."""
        if len(processed_list) == 1:
            return (None, processed_list[0])
        # Multiple items: return None to let normal list processing continue
        return None

    reg.register("process_list_field", "Extrusion.shape", process_extrusion_shape)

    return reg
