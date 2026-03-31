from cadbuildr.foundation import (
    Circle,
    Part,
    Point3D,
    Sketch,
    Thread,
)
from cadbuildr.foundation.dag_utils import show_dag
from cadbuildr.foundation.constants import DEFAULT_VALID_TYPES


def test_thread_macro_expands_to_sweep_for_default_dag_types():
    part = Part()
    sketch = Sketch(part.xz())
    profile = Circle(sketch.origin, 0.5)
    thread = Thread(
        profile=profile,
        pitch=1.25,
        height=8.0,
        radius=4.0,
        center=Point3D(0.0, 0.0, 0.0),
        dir=Point3D(0.0, 0.0, 1.0),
    )
    part.add_operation(thread)

    dag = show_dag(part)

    assert "Thread" not in dag["serializableNodes"]
    assert "Sweep" in dag["serializableNodes"]
    assert "Helix3D" in dag["serializableNodes"]

    node_type_by_id = {type_id: type_name for type_name, type_id in dag["serializableNodes"].items()}
    dag_type_names = {node_type_by_id[node["type"]] for node in dag["DAG"].values()}

    assert "Thread" not in dag_type_names
    assert "Sweep" in dag_type_names
    assert "Helix3D" in dag_type_names


def test_thread_can_be_serialized_when_explicitly_allowed():
    part = Part()
    sketch = Sketch(part.xz())
    profile = Circle(sketch.origin, 0.5)
    thread = Thread(
        profile=profile,
        pitch=1.25,
        height=8.0,
        radius=4.0,
        center=Point3D(0.0, 0.0, 0.0),
        dir=Point3D(0.0, 0.0, 1.0),
    )
    # Bypass add_operation() expansion to verify serialization behavior.
    part.operations.append(thread)

    dag = show_dag(part, valid_types=[*DEFAULT_VALID_TYPES, "Thread"])
    node_type_by_id = {type_id: type_name for type_name, type_id in dag["serializableNodes"].items()}
    dag_type_names = {node_type_by_id[node["type"]] for node in dag["DAG"].values()}

    assert "Thread" in dag["serializableNodes"]
    assert "Thread" in dag_type_names
