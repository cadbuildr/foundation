"""Unit tests for DAG hooks system."""

from pydantic import BaseModel

from cadbuildr.foundation.gen.dag.hooks import (
    HookRegistry,
    TraversalContext,
    clear_hooks,
    register_hook,
    _global_registry,
)


class TestModel(BaseModel):
    """Test model for hook testing."""

    value: int = 42


def test_hook_registration():
    """Test that hooks can be registered and executed."""
    clear_hooks()

    call_count = {"count": 0}

    @register_hook("on_encounter", "TestModel")
    def test_hook(obj, context):
        call_count["count"] += 1

    context = TraversalContext(memo={}, type_registry={}, valid_types=set())

    obj = TestModel()
    _global_registry.run_hooks("on_encounter", obj, context)

    assert call_count["count"] == 1


def test_hook_with_multiple_types():
    """Test that hooks can be registered for multiple types."""
    clear_hooks()

    call_count = {"count": 0}

    @register_hook("on_encounter", ["TestModel", "BaseModel"])
    def test_hook(obj, context):
        call_count["count"] += 1

    context = TraversalContext(memo={}, type_registry={}, valid_types=set())

    obj = TestModel()
    _global_registry.run_hooks("on_encounter", obj, context)

    # Should be called once for TestModel match
    assert call_count["count"] == 1


def test_on_first_encounter():
    """Test that on_first_encounter only fires once per hash."""
    clear_hooks()

    call_count = {"count": 0}

    @register_hook("on_first_encounter", "TestModel")
    def test_hook(obj, context):
        call_count["count"] += 1

    context = TraversalContext(memo={}, type_registry={}, valid_types=set())

    obj = TestModel()

    # First encounter
    context.node_hash = "hash1"
    context.is_first_encounter = _global_registry.mark_encountered("hash1")
    if context.is_first_encounter:
        _global_registry.run_hooks("on_first_encounter", obj, context)

    # Second encounter with same hash
    context.is_first_encounter = _global_registry.mark_encountered("hash1")
    if context.is_first_encounter:
        _global_registry.run_hooks("on_first_encounter", obj, context)

    # Should only be called once
    assert call_count["count"] == 1
