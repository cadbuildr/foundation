"""Tests for slug-based naming of Part / Assembly subclasses.

When a user subclasses ``Part`` (e.g. ``class TableLeg(Part): ...``) the
assembly tree should display ``table_leg`` instead of ``part_<idx>``. Multiple
instances of the same subclass within an assembly get a 1-based numeric
suffix (``table_leg_1``, ``table_leg_2``, ...); a single unique subclass keeps
its bare slug (``table_top``).
"""

from cadbuildr.foundation.compute_functions import (  # pragma: allowlist secret
    _camel_to_snake,
    _convert_component_to_root,
    _finalize_root_names,
)
from cadbuildr.foundation.dag_utils import show_dag  # pragma: allowlist secret
from cadbuildr.foundation.gen.models import (  # pragma: allowlist secret
    Assembly,
    Extrusion,
    Part,
    PartRoot,
    AssemblyRoot,
    Sketch,
    Square,
)


class TableTop(Part):
    def __init__(self, size=120, thickness=3):
        super().__init__()
        sketch = Sketch(self.xy())
        square = Square.from_center_and_side(sketch.origin, size)
        self.add_operation(Extrusion(square, thickness))


class TableLeg(Part):
    def __init__(self, size=4, height=75):
        super().__init__()
        sketch = Sketch(self.xy())
        square = Square.from_center_and_side(sketch.origin, size)
        self.add_operation(Extrusion(square, height))


def _build_table_assembly(num_legs: int = 4) -> Assembly:
    table = Assembly()
    table.add_component(TableTop())
    for _ in range(num_legs):
        table.add_component(TableLeg())
    return table


def _root_child_names(root: AssemblyRoot) -> list[str]:
    return [child.name.value for child in root.components]


def test_camel_to_snake_basic_cases():
    assert _camel_to_snake("TableLeg") == "table_leg"
    assert _camel_to_snake("TableTop") == "table_top"
    assert _camel_to_snake("HTTPServer") == "http_server"
    assert _camel_to_snake("Brick") == "brick"


def test_unique_subclass_keeps_bare_slug():
    table = _build_table_assembly(num_legs=0)
    table.add_component(TableTop())  # only one extra -> still unique with the first
    # Build fresh: single TableTop
    fresh = Assembly()
    fresh.add_component(TableTop())
    converted = _convert_component_to_root(fresh)
    _finalize_root_names(converted)

    assert isinstance(converted, AssemblyRoot)
    assert _root_child_names(converted) == ["table_top"]


def test_colliding_subclass_gets_numeric_suffix():
    table = _build_table_assembly(num_legs=4)
    converted = _convert_component_to_root(table)
    _finalize_root_names(converted)

    assert isinstance(converted, AssemblyRoot)
    names = _root_child_names(converted)
    # One unique TableTop and four TableLegs
    assert names == [
        "table_top",
        "table_leg_1",
        "table_leg_2",
        "table_leg_3",
        "table_leg_4",
    ]


def test_base_part_class_falls_back_to_path_naming():
    # Direct ``Part()`` (no subclass) keeps the existing deterministic name
    # (``part_<path>``) instead of getting a slug. This preserves DAG hashing
    # behavior for unnamed primitives.
    part = Part()
    converted = _convert_component_to_root(part)
    _finalize_root_names(converted)

    assert isinstance(converted, PartRoot)
    # Path is empty for top-level conversion, so the existing fallback yields
    # ``part_root``.
    assert converted.name.value == "part_root"


def test_user_set_name_is_preserved():
    from cadbuildr.foundation.gen.models import StringParameter  # pragma: allowlist secret

    leg = TableLeg()
    leg.name = StringParameter(value="custom_leg")

    assy = Assembly()
    assy.add_component(leg)
    assy.add_component(TableLeg())
    converted = _convert_component_to_root(assy)
    _finalize_root_names(converted)

    names = _root_child_names(converted)
    # Custom name is untouched; the auto-named sibling is unique with its slug
    assert names == ["custom_leg", "table_leg"]


def test_finalize_is_idempotent():
    table = _build_table_assembly(num_legs=3)
    converted = _convert_component_to_root(table)

    _finalize_root_names(converted)
    first_pass = _root_child_names(converted)

    _finalize_root_names(converted)
    second_pass = _root_child_names(converted)

    assert first_pass == second_pass == [
        "table_top",
        "table_leg_1",
        "table_leg_2",
        "table_leg_3",
    ]


def test_show_dag_emits_slug_names_in_string_parameters():
    table = _build_table_assembly(num_legs=2)
    dag = show_dag(table)
    string_type = dag["serializableNodes"]["StringParameter"]
    string_values = {
        node.get("params", {}).get("value")
        for node in dag["DAG"].values()
        if node["type"] == string_type
    }
    assert "table_top" in string_values
    assert "table_leg_1" in string_values
    assert "table_leg_2" in string_values


def test_uniqueness_scope_is_per_assembly():
    # A nested assembly should get its own naming scope: a single TableLeg in
    # an inner assembly stays as ``table_leg`` even if the outer assembly has
    # other TableLegs.
    inner = Assembly()
    inner.add_component(TableLeg())

    outer = Assembly()
    outer.add_component(TableLeg())
    outer.add_component(TableLeg())
    outer.add_component(inner)

    converted = _convert_component_to_root(outer)
    _finalize_root_names(converted)

    outer_names = _root_child_names(converted)
    # Two outer TableLegs collide; the inner Assembly is the third child
    assert outer_names[:2] == ["table_leg_1", "table_leg_2"]
    inner_root = converted.components[2]
    assert isinstance(inner_root, AssemblyRoot)
    assert _root_child_names(inner_root) == ["table_leg"]


def test_subclassed_assembly_gets_slug_name():
    class Table(Assembly):
        def __init__(self):
            super().__init__()
            self.add_component(TableTop())

    parent = Assembly()
    parent.add_component(Table())
    parent.add_component(Table())
    converted = _convert_component_to_root(parent)
    _finalize_root_names(converted)

    assert _root_child_names(converted) == ["table_1", "table_2"]


def test_unrelated_default_name_unchanged_when_no_subclass():
    # Sanity: the root Assembly still ends up with the path-based fallback
    # since ``Assembly()`` is the base class.
    assy = Assembly()
    assy.add_component(Part())
    converted = _convert_component_to_root(assy)
    _finalize_root_names(converted)

    assert isinstance(converted, AssemblyRoot)
    assert converted.name.value == "assy_root"
