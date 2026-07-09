"""Serialization tests for anchors + joints: determinism, distinct placements,
stable type ids, and acyclicity."""

import json

from cadbuildr.foundation.constants import DEFAULT_TYPE_REGISTRY
from cadbuildr.foundation.dag_utils import show_dag
from cadbuildr.foundation.gen.models import (
    Anchor,
    Assembly,
    BoolParameter,
    Extrusion,
    Frame,
    Part,
    RigidJoint,
    Sketch,
    Square,
    StringParameter,
)

FLIP_Q = [0.0, 1.0, 0.0, 0.0]  # 180° about X


class Brick(Part):
    def __init__(self, size=8.0, height=9.6):
        super().__init__()
        sketch = Sketch(self.xy())
        square = Square.from_center_and_side(sketch.origin, size)
        self.add_operation(Extrusion(square, height))
        self.add_anchor(_anchor("top", [0, 0, height]))
        self.add_anchor(_anchor("bottom", [0, 0, 0], FLIP_Q))


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


def make_tower(n=3):
    assembly = Assembly()
    bricks = [Brick() for _ in range(n)]
    assembly.add_component(bricks[0])
    for below, above in zip(bricks, bricks[1:]):
        assembly.add_joint(
            RigidJoint(
                parent_anchor=below.anchor("top"),
                child_anchor=above.anchor("bottom"),
            )
        )
    return assembly


def test_jointed_assembly_dag_is_deterministic():
    dag1 = show_dag(make_tower(4))
    dag2 = show_dag(make_tower(4))
    assert dag1 == dag2


def test_identical_stacked_bricks_have_distinct_frames():
    dag = show_dag(make_tower(3))
    part_type = dag["serializableNodes"]["PartRoot"]
    part_ids = [nid for nid, n in dag["DAG"].items() if n["type"] == part_type]
    assert len(part_ids) == 3, (
        "Three identical bricks at different heights must serialize as three "
        "distinct PartRoot nodes (frames differ), not alias to one hash."
    )


def test_joints_and_anchors_serialized_on_roots():
    dag = show_dag(make_tower(2))
    root = dag["DAG"][dag["rootNodeId"]]
    joints = root.get("deps", {}).get("joints", [])
    assert len(joints) == 1
    joint_node = dag["DAG"][joints[0]]
    assert joint_node["type"] == dag["serializableNodes"]["RigidJoint"]
    assert "parent_anchor" in joint_node["deps"]
    assert "child_anchor" in joint_node["deps"]

    part_type = dag["serializableNodes"]["PartRoot"]
    for nid, node in dag["DAG"].items():
        if node["type"] == part_type:
            assert len(node["deps"].get("anchors", [])) == 2


def test_type_ids_are_stable_and_appended():
    # The legacy prefix of the registry must never shift: joint types are
    # strictly appended after the last pre-anchor type.
    assert DEFAULT_TYPE_REGISTRY["Part"] == 0
    assert DEFAULT_TYPE_REGISTRY["FullRound"] < DEFAULT_TYPE_REGISTRY["Anchor"]
    assert (
        DEFAULT_TYPE_REGISTRY["Anchor"]
        < DEFAULT_TYPE_REGISTRY["JointLimits"]
        < DEFAULT_TYPE_REGISTRY["RigidJoint"]
        < DEFAULT_TYPE_REGISTRY["ScrewJoint"]
    )


def test_dag_is_json_serializable_and_acyclic():
    # pydantic_to_dag raises on true object cycles; reaching json.dumps at
    # all proves the anchor/joint back-references stayed transient.
    dag = show_dag(make_tower(3))
    encoded = json.dumps(dag)
    assert "RigidJoint" in json.dumps(dag["serializableNodes"])
    assert len(encoded) > 0
