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

    # An empty ``interfaces`` list (most components) is not written, so the
    # DAG of a component without interfaces is the same as before they existed.
    def skip_empty_interfaces(
        field_name: str, obj: BaseModel, context: TraversalContext
    ) -> bool:
        return field_name == "interfaces" and not getattr(obj, "interfaces", None)

    reg.register("should_skip_field", "*", skip_empty_interfaces)

    # A CompactPolygon / CompactPolyline that a kernel reads natively is
    # written as coords + bulges only; its Line/Arc `primitives` are the
    # lowering, and writing them would undo the compaction.
    def skip_compact_primitives(
        field_name: str, obj: BaseModel, context: TraversalContext
    ) -> bool:
        return field_name == "primitives"

    for compact in ("CompactPolygon", "CompactPolyline"):
        reg.register("should_skip_field", compact, skip_compact_primitives)

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

    # A constrained sketch is solved before any of its geometry is written: an
    # operation can reach a sketch's points (through its shape) before the
    # Sketch node itself, and those points must already hold solved values.
    def solve_sketch_before_elements(obj: BaseModel, context: TraversalContext) -> None:
        # Any node with a sketch (an Extrusion, a shape, a point): reached before the
        # shapes an expansion may copy, so the copies carry solved values too.
        if "sketch" not in type(obj).model_fields:
            return
        sketch = getattr(obj, "sketch", None)
        if type(sketch).__name__ == "Sketch" and getattr(sketch, "constraints", None):
            if getattr(sketch, "solve_status", None) is None:
                # As conversion computes a None @compute field; stored so it runs once.
                object.__setattr__(
                    sketch, "solve_status", sketch.compute("solve_status")
                )

    # Hooks are looked up by exact type name: register for every type with a sketch.
    from cadbuildr.foundation.gen import models

    with_sketch = [
        name
        for name, cls in vars(models).items()
        if isinstance(cls, type)
        and issubclass(cls, BaseModel)
        and "sketch" in getattr(cls, "model_fields", {})
    ]
    reg.register("on_encounter", with_sketch, solve_sketch_before_elements)

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
