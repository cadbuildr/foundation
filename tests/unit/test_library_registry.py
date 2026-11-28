"""cadbuildr.foundation.library: widgets, manifest, configurations, bindings, library_ref."""

from __future__ import annotations

import dataclasses
import enum
import json
import os
import subprocess
import sys
import textwrap

import pytest
from typing import ClassVar, Literal, Optional


from cadbuildr.foundation import (
    Assembly,
    Circle,
    Extrusion,
    Part,
    Point,
    Sketch,
    make_anchor,
    show_dag,
)
from cadbuildr.foundation.library import (
    Color,
    InputOf,
    Num,
    OneOf,
    assembly,
    get_manifest,
    item_for,
    operation,
    part,
    stamp_of,
    widget_for,
)
from cadbuildr.foundation.library.evaluate import evaluate
from cadbuildr.foundation.library.registry import (
    MANIFEST_FORMAT,
    library_id_for,
    parse_docstring,
)

# --------------------------------------------------------------------------- #
# Fixtures: a tiny library declared in this module
# --------------------------------------------------------------------------- #


@part(
    category="Bearings/Ball",
    name="Test bearing",
    standard="ISO 15",
    configurations={"Big one": dict(model="b2")},
)
class TBearing(Part):
    """A test bearing.

    Args:
        model: bearing designation.
        width: ring width.
    """

    TABLE: ClassVar[dict] = {"a1": {"d": 3.0, "D": 10.0}, "b2": {"d": 5.0, "D": 16.0}}

    def __init__(
        self, model: OneOf[TABLE] = "a1", width: Num(min=1, max=10, step=0.5) = 4.0
    ):
        b = self.TABLE[model]
        self.add_operation(
            Extrusion(Circle(Point(Sketch(self.xy()), 0, 0), b["D"] / 2), width)
        )
        self.add_anchor(make_anchor("axis", (0.0, 0.0, 0.0)))
        self.add_anchor(make_anchor("top", (0.0, 0.0, width)))


@assembly(category="Demo")
class TBoard(Assembly):
    def __init__(
        self, bearing: InputOf[TBearing, "model"] = "b2", gap: float = 10.0
    ):  # noqa: F821
        for i in range(2):
            b = TBearing(model=bearing)  # bound by name
            b.translate([i * gap, 0.0, 0.0])
            self.add_component(b)
        literal = TBearing(model="b2")  # a literal: never bound, even if equal
        literal.translate([0.0, 50.0, 0.0])
        self.add_component(literal)
        alias = bearing
        via_alias = TBearing(alias)  # same object, other name: bound by identity
        via_alias.translate([0.0, 90.0, 0.0])
        self.add_component(via_alias)


class Plain(Part):
    def __init__(self, r: float = 5.0):
        self.add_operation(Extrusion(Circle(Point(Sketch(self.xy()), 0, 0), r), 2.0))


class Finish(enum.Enum):
    MATTE = 1
    GLOSS = 2


@dataclasses.dataclass
class Spec:
    length: float = 10.0
    count: int = 2
    through: bool = False
    face: Literal["px", "nx"] = "px"


@operation(category="Joints")
def join(a: TBearing, b: TBearing, spec: Spec = Spec(), side: Literal["l", "r"] = "l"):
    """Join two bearings."""
    return None


# --------------------------------------------------------------------------- #
# Widgets
# --------------------------------------------------------------------------- #


def test_widgets_from_hints():
    assert widget_for(OneOf[{"x": 1, "y": 2}], "y") == {
        "kind": "enum",
        "options": ["x", "y"],
        "default": "y",
    }
    assert widget_for(OneOf[[3, 5, 8]], 5) == {
        "kind": "enum",
        "options": ["3", "5", "8"],
        "default": "5",
    }
    assert widget_for(Literal["a", "b"], "b") == {
        "kind": "enum",
        "options": ["a", "b"],
        "default": "b",
    }
    assert widget_for(Finish, Finish.GLOSS) == {
        "kind": "enum",
        "options": ["MATTE", "GLOSS"],
        "default": "GLOSS",
    }
    assert widget_for(float, 2.5) == {
        "kind": "number",
        "integer": False,
        "default": 2.5,
        "unit": "mm",
    }
    assert widget_for(int, 3) == {"kind": "number", "integer": True, "default": 3}
    assert widget_for(bool, True) == {"kind": "bool", "default": True}
    assert widget_for(str, "hi") == {"kind": "text", "default": "hi"}
    assert widget_for(Num, 54) == {
        "kind": "number",
        "integer": False,
        "default": 54,
        "unit": "mm",
    }
    assert widget_for(Num(min=3, max=80, step=1, unit="deg"), 20) == {
        "kind": "number",
        "integer": False,
        "default": 20,
        "unit": "deg",
        "min": 3,
        "max": 80,
        "step": 1,
    }
    color = widget_for(Color, "red")
    assert (
        color["kind"] == "enum"
        and "red" in color["options"]
        and color["default"] == "red"
    )
    assert widget_for(Optional[float], None) == {
        "kind": "number",
        "integer": False,
        "default": None,
        "unit": "mm",
        "optional": True,
    }
    assert widget_for(TBearing) == {
        "kind": "existing",
        "type": "TBearing",
        "lookup": "pick",
    }
    obj = widget_for(Spec, Spec())
    assert obj["kind"] == "object" and obj["type"] == "Spec"
    assert [f["name"] for f in obj["fields"]] == ["length", "count", "through", "face"]
    assert obj["fields"][3]["widget"] == {
        "kind": "enum",
        "options": ["px", "nx"],
        "default": "px",
    }
    assert obj["fields"][0] == {
        "name": "length",
        "label": "Length",
        "widget": {"kind": "number", "integer": False, "default": 10.0, "unit": "mm"},
        "required": False,
        "hasDefault": True,
    }
    # No hint: inferred from the default.
    import inspect

    assert widget_for(inspect.Parameter.empty, True) == {
        "kind": "bool",
        "default": True,
    }


def test_input_of_uses_the_referenced_widget():
    board = item_for(TBoard)
    widget = board.input("bearing")["widget"]
    assert widget["kind"] == "enum"
    assert widget["options"] == ["a1", "b2"]
    assert widget["default"] == "b2"
    assert widget["inputOf"] == {"item": item_for(TBearing).id, "input": "model"}


def test_docstring_args_become_descriptions():
    summary, args = parse_docstring(TBearing.__doc__)
    assert summary == "A test bearing."
    assert args == {"model": "bearing designation.", "width": "ring width."}
    assert item_for(TBearing).input("width")["description"] == "ring width."


# --------------------------------------------------------------------------- #
# Configurations and manifest
# --------------------------------------------------------------------------- #


def test_configurations_presets_then_table_rows():
    item = item_for(TBearing)
    assert item.configurations() == [
        {"name": "Big one", "values": {"model": "b2"}},
        {"name": "a1", "values": {"model": "a1"}},
        {"name": "b2", "values": {"model": "b2"}},
    ]
    assert item.match_configuration({"model": "a1", "width": 4.0}) == "a1"
    assert item.match_configuration({"model": "b2", "width": 4.0}) == "Big one"
    # Another input off its default: no configuration matches.
    assert item.match_configuration({"model": "a1", "width": 6.0}) is None


def _lib() -> str:
    """The library id this module's items carry (depends on how pytest/Bazel imported it)."""
    return item_for(TBearing).id.rsplit(":", 1)[0]


def test_manifest_item_snapshot():
    manifest = get_manifest(__name__)
    assert manifest["format"] == MANIFEST_FORMAT
    lib = manifest["library"]
    assert lib["import_root"] == __name__ and lib["id"] == library_id_for(__name__)
    items = {i["cls"]: i for i in manifest["items"]}
    assert set(items) >= {"TBearing", "TBoard", "join"}
    assert items["TBearing"] == {
        "id": f"{_lib()}:TBearing",
        "kind": "part",
        "module": __name__,
        "cls": "TBearing",
        "name": "Test bearing",
        "category": "Bearings/Ball",
        "standard": "ISO 15",
        "description": "A test bearing.",
        "inputs": [
            {
                "name": "model",
                "label": "Model",
                "required": False,
                "hasDefault": True,
                "widget": {"kind": "enum", "options": ["a1", "b2"], "default": "a1"},
                "description": "bearing designation.",
            },
            {
                "name": "width",
                "label": "Width",
                "required": False,
                "hasDefault": True,
                "widget": {
                    "kind": "number",
                    "integer": False,
                    "default": 4.0,
                    "unit": "mm",
                    "min": 1,
                    "max": 10,
                    "step": 0.5,
                },
                "description": "ring width.",
            },
        ],
        "configurations": [
            {"name": "Big one", "values": {"model": "b2"}},
            {"name": "a1", "values": {"model": "a1"}},
            {"name": "b2", "values": {"model": "b2"}},
        ],
        "thumbnail": None,
        "anchors": ["axis", "top"],
        "interfaces": [],
    }
    assert items["join"]["kind"] == "operation"
    spec_input = items["join"]["inputs"][2]
    assert spec_input["widget"]["kind"] == "object"
    assert items["join"]["inputs"][0]["widget"] == {
        "kind": "existing",
        "type": "TBearing",
        "lookup": "pick",
    }
    # Default toolbar: one section per top-level category.
    sections = {s["id"]: s for s in manifest["toolbar"]["sections"]}
    assert f"{_lib()}:TBearing" in sections["bearings"]["items"]
    assert sections["bearings"]["label"] == "Bearings"
    json.dumps(manifest)  # JSON-serializable


# --------------------------------------------------------------------------- #
# Stamps, bindings and the DAG
# --------------------------------------------------------------------------- #


def _library_refs(dag: dict) -> list[dict]:
    names = {v: k for k, v in dag["serializableNodes"].items()}
    nodes = dag["DAG"]
    out = []
    for node in nodes.values():
        if (
            names[node["type"]] in ("PartRoot", "AssemblyRoot")
            and "library" in node["deps"]
        ):
            ref = nodes[node["deps"]["library"]]
            out.append({k: nodes[v]["params"]["value"] for k, v in ref["deps"].items()})
    return out


def test_bindings_parent_assembly_drives_bearings():
    board = TBoard(bearing="a1")
    stamps = [
        stamp_of(c.__dict__.get("_source_component", c)) for c in board.components
    ]
    assert [s["inputs"]["model"] for s in stamps] == ["a1", "a1", "b2", "a1"]
    assert stamps[0]["bindings"] == {"model": "bearing"}
    assert stamps[1]["bindings"] == {"model": "bearing"}
    assert stamps[2]["bindings"] is None  # literal "b2"
    assert stamps[3]["bindings"] == {"model": "bearing"}  # same object
    assert stamps[0]["configuration"] == "a1"
    top = stamp_of(board)
    assert top["inputs"] == {"bearing": "a1", "gap": 10.0}
    assert top["bindings"] is None


def test_library_ref_in_dag():
    dag = show_dag(TBoard(bearing="a1"))
    refs = _library_refs(dag)
    by_cls = {}
    for ref in refs:
        by_cls.setdefault(ref["cls"], []).append(ref)
    board = by_cls["TBoard"][0]
    assert board["item"] == f"{_lib()}:TBoard"
    assert json.loads(board["inputs"]) == {"bearing": "a1", "gap": 10.0}
    bearings = by_cls["TBearing"]
    assert {r["inputs"] for r in bearings} == {
        json.dumps({"model": "a1", "width": 4.0}),
        json.dumps({"model": "b2", "width": 4.0}),
    }
    bound = [r for r in bearings if "bindings" in r]
    assert bound and all(
        json.loads(r["bindings"]) == {"model": "bearing"} for r in bound
    )
    assert all(r["module"] == __name__ for r in bearings)


def test_undecorated_dag_has_no_library_and_same_ids():
    dag = show_dag(Plain())
    assert _library_refs(dag) == []
    names = {v: k for k, v in dag["serializableNodes"].items()}
    assert not any(names[n["type"]] == "LibraryRef" for n in dag["DAG"].values())
    # The type ids of existing node types are unchanged (LibraryRef is appended).
    registry = dag["serializableNodes"]
    # (Interface is appended after it.)
    assert registry["LibraryRef"] == registry["Interface"] - 1
    assert registry["Interface"] == max(registry.values())
    assert show_dag(Plain())["rootNodeId"] == dag["rootNodeId"]


def test_subclass_of_decorated_class_is_not_stamped_as_parent():
    class Sub(TBearing):
        def __init__(self):
            super().__init__(model="b2")

    assert stamp_of(Sub()) is None


def test_library_source_recorded_for_installed_module():
    stamp = stamp_of(TBearing())
    # A test module is not an installed library: its folder (a git checkout
    # here: "git <remote>@<sha>[ dirty]"), or nothing.
    if "." in __name__:
        pytest.skip("imported as a package (Bazel): its root is not a library folder")
    assert stamp["source"] is None or stamp["source"].startswith(("local ", "git "))


# --------------------------------------------------------------------------- #
# Evaluate / CLI
# --------------------------------------------------------------------------- #


def test_evaluate_in_process():
    result = evaluate(
        {"item": f"{_lib()}:TBearing", "inputs": {"model": "b2", "width": "6"}}
    )
    assert result["ok"], result
    refs = _library_refs(result["dag"])
    assert json.loads(refs[0]["inputs"]) == {"model": "b2", "width": 6.0}
    assert evaluate({"item": f"{_lib()}:join", "inputs": {}}) == {
        "ok": False,
        "error": "operations are not evaluable alone",
    }
    bad = evaluate({"item": "nope:Nothing", "inputs": {}})
    assert bad["ok"] is False and "unknown library item" in bad["error"]


LIB_SOURCE = textwrap.dedent("""
    from cadbuildr.foundation import Part, Sketch, Circle, Point, Extrusion
    from cadbuildr.foundation.library import part, Num, OneOf

    @part(category="Wheels")
    class Wheel(Part):
        def __init__(self, diameter: Num(min=10, max=90) = 54, seat: OneOf[["608", "6800"]] = "608"):
            self.add_operation(Extrusion(Circle(Point(Sketch(self.xy()), 0, 0), diameter / 2), 10))
    """)


def test_cli_eval_and_manifest_round_trip(tmp_path):
    pkg = tmp_path / "cli_demo_lib"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "wheels.py").write_text(LIB_SOURCE)
    env = {
        **os.environ,
        "PYTHONPATH": f"{tmp_path}{os.pathsep}{os.environ.get('PYTHONPATH', '')}",
    }
    run = lambda args, stdin=None: subprocess.run(  # noqa: E731
        [sys.executable, "-m", "cadbuildr.foundation.library", *args],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
    )
    proc = run(["manifest", "cli_demo_lib"])
    assert proc.returncode == 0, proc.stderr
    manifest = json.loads(proc.stdout)
    assert [i["id"] for i in manifest["items"]] == ["cli_demo_lib:Wheel"]
    assert manifest["toolbar"]["sections"][0]["items"] == ["cli_demo_lib:Wheel"]

    proc = run(
        ["eval"],
        json.dumps(
            {"item": "cli_demo_lib:Wheel", "inputs": {"diameter": 60, "seat": "6800"}}
        ),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = json.loads(proc.stdout)
    assert result["ok"] is True
    root = result["dag"]["DAG"][result["dag"]["rootNodeId"]]
    names = {v: k for k, v in result["dag"]["serializableNodes"].items()}
    assert names[root["type"]] == "PartRoot"
    ref = _library_refs(result["dag"])[0]
    assert ref["item"] == "cli_demo_lib:Wheel"
    assert json.loads(ref["inputs"]) == {"diameter": 60, "seat": "6800"}

    # Every command prints one JSON line; failures are data (exit 0).
    proc = run(["eval"], "not json")
    assert proc.returncode == 0 and json.loads(proc.stdout)["ok"] is False
    assert len(proc.stdout.strip().splitlines()) == 1


def test_cadbuildr_project_alias_registers_a_library_item():
    from cadbuildr.foundation import Int, cadbuildr_project

    @cadbuildr_project(title="Discs", parameters=[Int("n", default=2, min=1, max=5)])
    def discs(n: int = 2):
        return Plain(r=float(n))

    items = {
        i.cls: i
        for i in __import__("cadbuildr.foundation.library", fromlist=["items"]).items(
            __name__
        )
    }
    item = next(i for k, i in items.items() if k.endswith("discs"))
    assert item.kind == "project"
    assert item.input("n")["widget"] == {
        "kind": "number",
        "integer": True,
        "default": 2,
        "min": 1,
        "max": 5,
        "step": 1,
    }
    result = evaluate({"item": item.id, "inputs": {"n": 3}})
    assert result["ok"], result
