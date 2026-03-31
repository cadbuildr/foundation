import re

from cadbuildr.foundation.dag_utils import show_dag
from cadbuildr.foundation.gen.models import Assembly, Extrusion, Part, Sketch, Square


class Brick(Part):
    def __init__(self, size=8, height=8):
        super().__init__()
        sketch = Sketch(self.xy())
        square = Square.from_center_and_side(sketch.origin, size)
        self.add_operation(Extrusion(square, height))


def make_many_bricks_assy(n=16):
    assy = Assembly()
    for i in range(n):
        brick = Brick()
        brick.translate([float(i * 10), 0.0, 0.0])
        assy.add_component(brick)
    return assy


def _collect_string_parameter_values(dag):
    string_type = dag["serializableNodes"]["StringParameter"]
    values = []
    for node in dag["DAG"].values():
        if node["type"] == string_type:
            value = node.get("params", {}).get("value")
            if isinstance(value, str):
                values.append(value)
    return values


def test_many_identical_parts_dag_is_deterministic():
    dag1 = show_dag(make_many_bricks_assy(20))
    dag2 = show_dag(make_many_bricks_assy(20))

    assert dag1 == dag2, "DAG should be deterministic for repeated identical assemblies."


def test_many_identical_parts_no_object_id_based_names():
    dag = show_dag(make_many_bricks_assy(20))
    string_values = _collect_string_parameter_values(dag)

    object_id_like_patterns = [
        re.compile(r"^component_\d{7,}_origin$"),
        re.compile(r"^assembly_\d{7,}_frame$"),
    ]

    offenders = [
        value
        for value in string_values
        if any(pattern.match(value) for pattern in object_id_like_patterns)
    ]

    assert not offenders, (
        "Found object-id based names in DAG string parameters. "
        f"Offenders: {offenders[:10]}"
    )
