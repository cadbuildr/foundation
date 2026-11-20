"""Regression tests: edits made to a Part/Assembly *after* it was placed in an
assembly (``add_component`` / ``add_joint``) must reach the serialized DAG.

Placement converts the component to a PartRoot/AssemblyRoot eagerly; these
tests pin that the root stays live instead of snapshotting the component.
"""

from cadbuildr.foundation.dag_utils import pydantic_to_dag, show_dag
from cadbuildr.foundation.foundation_hooks import setup_foundation_hooks
from cadbuildr.foundation.gen.models import (
    Anchor,
    Assembly,
    BoolParameter,
    Circle,
    Extrusion,
    Frame,
    Part,
    RigidJoint,
    Sketch,
    Square,
    StringParameter,
)

FLIP_Q = [0.0, 1.0, 0.0, 0.0]


def _anchor(name, position, quaternion=(1.0, 0.0, 0.0, 0.0)):
    return Anchor(
        frame=Frame(
            top_frame=None,
            name=StringParameter(value=f"anchor_{name}_frame"),
            display=BoolParameter(value=False),
            position=list(position),
            quaternion=list(quaternion),
        ),
        name=StringParameter(value=name),
    )


def _block(size=20.0, height=10.0):
    part = Part()
    sketch = Sketch(part.xy())
    part.add_operation(
        Extrusion(Square.from_center_and_side(sketch.origin, size), height)
    )
    part.add_anchor(_anchor("top", [0, 0, height]))
    part.add_anchor(_anchor("bottom", [0, 0, 0], FLIP_Q))
    return part


def _cut(part, radius=2.0, depth=4.0):
    """Add a cut extrusion (a hole) to ``part`` and return it."""
    sketch = Sketch(part.xy())
    op = Extrusion(Circle(sketch.origin, radius), depth, cut=True)
    part.add_operation(op)
    return op


def _nodes(dag, type_name):
    type_id = dag["serializableNodes"][type_name]
    return {nid: n for nid, n in dag["DAG"].items() if n["type"] == type_id}


def _part_root_op_counts(dag):
    return sorted(
        len(n["deps"]["operations"]) for n in _nodes(dag, "PartRoot").values()
    )


def _has_cut(dag):
    true_ids = {
        nid
        for nid, n in _nodes(dag, "BoolParameter").items()
        if n["params"].get("value") is True
    }
    return any(n["deps"]["cut"] in true_ids for n in _nodes(dag, "Extrusion").values())


def test_cut_added_after_add_component_reaches_dag():
    part = _block()
    assembly = Assembly()
    assembly.add_component(part)
    assert not _has_cut(show_dag(assembly))

    _cut(part)

    dag = show_dag(assembly)
    assert _part_root_op_counts(dag) == [2]
    assert _has_cut(dag)


def test_late_operation_visible_on_root_and_to_dag():
    part = _block()
    assembly = Assembly()
    assembly.add_component(part)
    op = _cut(part)

    # The placed root shares the part's operations — no re-sync needed.
    assert assembly.components[0].operations[-1] is op
    memo = assembly.to_dag()
    part_roots = [n for n in memo.values() if "operations" in n.get("deps", {})]
    assert [len(n["deps"]["operations"]) for n in part_roots] == [2]


def test_late_operation_reaches_bare_pydantic_to_dag():
    """Even without the re-conversion pass, the root sees the new op."""
    part = _block()
    assembly = Assembly()
    assembly.add_component(part)
    _cut(part)
    memo, type_registry = {}, {}
    pydantic_to_dag(
        assembly.components[0], memo, type_registry, setup_foundation_hooks()
    )
    part_roots = [n for n in memo.values() if n["type"] == type_registry["PartRoot"]]
    assert [len(n["deps"]["operations"]) for n in part_roots] == [2]


def test_extrusion_added_after_add_joint_reaches_dag():
    base, top = _block(), _block()
    assembly = Assembly()
    assembly.add_component(base)
    assembly.add_joint(
        RigidJoint(parent_anchor=base.anchor("top"), child_anchor=top.anchor("bottom"))
    )

    sketch = Sketch(top.xy())
    top.add_operation(Extrusion(Square.from_center_and_side(sketch.origin, 5.0), 30.0))
    _cut(base)

    assert _part_root_op_counts(show_dag(assembly)) == [2, 2]


def test_same_part_added_twice_both_instances_get_late_cut():
    part = _block()
    assembly = Assembly()
    assembly.add_component(part)
    assembly.add_component(part)

    _cut(part)

    roots = assembly.components
    assert len(roots) == 2
    assert all(len(r.operations) == 2 for r in roots)
    dag = show_dag(assembly)
    assert _has_cut(dag)
    assembly_node = _nodes(dag, "AssemblyRoot")[dag["rootNodeId"]]
    for child_id in assembly_node["deps"]["components"]:
        assert len(dag["DAG"][child_id]["deps"]["operations"]) == 2


def test_nested_assembly_late_cut_on_inner_part():
    part = _block()
    inner = Assembly()
    inner.add_component(part)
    outer = Assembly()
    outer.add_component(inner)

    _cut(part)

    dag = show_dag(outer)
    assert _part_root_op_counts(dag) == [2]
    assert _has_cut(dag)


def test_nested_assembly_component_added_after_placement():
    inner = Assembly()
    inner.add_component(_block())
    outer = Assembly()
    outer.add_component(inner)
    outer.translate([100.0, 0.0, 0.0])

    late = _block(size=5.0)
    inner.add_component(late)
    _cut(late)

    dag = show_dag(outer)
    assert _part_root_op_counts(dag) == [1, 2]

    # The late part chains to the placed inner assembly's frame, which in turn
    # chains to the outer assembly — not to the inner Assembly's own frame.
    inner_root = outer.components[0]
    late_root = inner_root.components[1]
    assert late_root.frame.top_frame is inner_root.frame


def test_paint_after_placement_reaches_root():
    part = _block()
    assembly = Assembly()
    assembly.add_component(part)
    part.paint("red")
    dag = show_dag(assembly)
    assert len(_nodes(dag, "Material")) == 1
