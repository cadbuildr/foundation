"""Source capture: DAG nodes point back at the user code that built them."""

import json
import os
import runpy
import subprocess
import sys
import textwrap

import pytest

from cadbuildr.foundation import show_dag, source_capture
from cadbuildr.foundation.gen.dag.conversion import SOURCE_NODE_KEYS

MODEL = textwrap.dedent("""\
    from cadbuildr.foundation import Part, Sketch, Square, Extrusion, FloatParameter

    width = 12


    class Block(Part):
        def __init__(self):
            s = Sketch(self.xy())
            sq = Square.from_center_and_side(s.origin, 30)
            self.add_operation(Extrusion(sq, 10))
            s2 = Sketch(self.xy())
            sq2 = Square.from_center_and_side(s2.origin, 5)
            self.extrude(sq2, width)
            depth = FloatParameter(7)
            self.add_operation(Extrusion(sq, depth))
            self.add_operation(Extrusion(sq2, end=depth, cut=True))
            self.add_operation(
                Extrusion(
                    sq,
                    end=width * 2,
                )
            )


    part = Block()
    """)


# Columns, source text and fieldSrc come from code positions (co_positions),
# which Python 3.10 lacks: there capture records only ``file`` + ``line``.
needs_columns = pytest.mark.skipif(
    sys.version_info < (3, 11), reason="columns and fieldSrc need Python 3.11+"
)


def _line_of(source: str, needle: str) -> int:
    for number, line in enumerate(source.splitlines(), start=1):
        if needle in line:
            return number
    raise AssertionError(needle)


@pytest.fixture
def project(tmp_path, monkeypatch):
    path = tmp_path / "model.py"
    path.write_text(MODEL)
    monkeypatch.chdir(tmp_path)
    return path


@pytest.fixture
def capture():
    with source_capture.capturing():
        yield
    assert not source_capture.is_enabled()


def _build(path, *, with_source=None):
    namespace = runpy.run_path(str(path))
    return show_dag(namespace["part"], with_source=with_source)


def _nodes_of(dag, type_name):
    type_id = dag["serializableNodes"][type_name]
    return [n for n in dag["DAG"].values() if n["type"] == type_id]


def _extrusion_with_end_text(dag, text):
    found = [
        n
        for n in _nodes_of(dag, "Extrusion")
        if n.get("fieldSrc", {}).get("end", {}).get("text") == text
    ]
    assert len(found) == 1, [n.get("fieldSrc") for n in _nodes_of(dag, "Extrusion")]
    return found[0]


def _assert_ref_points_at_text(ref, source):
    line = source.splitlines()[ref["line"] - 1]
    assert line[ref["col"] : ref["endCol"]] == ref["text"]


@needs_columns
def test_literal_argument_maps_to_owner_field(project, capture):
    dag = _build(project)
    node = _extrusion_with_end_text(dag, "10")
    line = _line_of(MODEL, "Extrusion(sq, 10)")

    col = MODEL.splitlines()[line - 1].index("Extrusion(sq, 10)")
    assert node["src"] == {
        "file": "model.py",
        "line": line,
        "col": col,
        "endCol": col + len("Extrusion(sq, 10)"),
        "text": "Extrusion(sq, 10)",
    }
    end = node["fieldSrc"]["end"]
    assert end["file"] == "model.py" and end["line"] == line
    _assert_ref_points_at_text(end, MODEL)
    assert node["fieldSrc"]["shape"]["text"] == "sq"


@needs_columns
def test_variable_argument_text_is_the_variable_name(project, capture):
    dag = _build(project)

    # Through a method whose parameter name ("depth") differs from the field
    # ("end"): matched by value.
    method_node = _extrusion_with_end_text(dag, "width")
    assert method_node["src"]["text"] == "self.extrude(sq2, width)"
    assert method_node["fieldSrc"]["shape"]["text"] == "sq2"
    _assert_ref_points_at_text(method_node["fieldSrc"]["end"], MODEL)

    # Keyword argument spread over several lines: expression text, own line.
    multi = _extrusion_with_end_text(dag, "width * 2")
    assert multi["fieldSrc"]["end"]["line"] == _line_of(MODEL, "end=width * 2")
    _assert_ref_points_at_text(multi["fieldSrc"]["end"], MODEL)
    assert "endCol" not in multi["src"]  # the call spans several lines


@needs_columns
def test_shared_parameter_is_one_node_with_per_owner_locations(project, capture):
    dag = _build(project)
    owners = [
        n
        for n in _nodes_of(dag, "Extrusion")
        if n.get("fieldSrc", {}).get("end", {}).get("text") == "depth"
    ]

    assert len(owners) == 2
    assert owners[0]["deps"]["end"] == owners[1]["deps"]["end"]  # one param node
    lines = sorted(o["fieldSrc"]["end"]["line"] for o in owners)
    assert lines == [
        _line_of(MODEL, "Extrusion(sq, depth)"),
        _line_of(MODEL, "Extrusion(sq2, end=depth"),
    ]
    cut_owner = next(o for o in owners if "cut" in o["fieldSrc"])
    assert cut_owner["fieldSrc"]["cut"]["text"] == "True"

    param = dag["DAG"][owners[0]["deps"]["end"]]
    assert param["params"] == {"value": 7.0}
    assert param["src"]["text"] == "FloatParameter(7)"


@needs_columns
def test_root_points_at_the_part_construction(project, capture):
    dag = _build(project)
    root = dag["DAG"][dag["rootNodeId"]]
    assert root["src"]["line"] == _line_of(MODEL, "part = Block()")
    assert root["src"]["text"] == "Block()"


def _strip_source(dag):
    stripped = json.loads(json.dumps(dag))
    for node in stripped["DAG"].values():
        for key in SOURCE_NODE_KEYS:
            node.pop(key, None)
    return stripped


def test_ids_and_hashes_identical_with_and_without_capture(project):
    plain = _build(project)
    with source_capture.capturing():
        captured = _build(project)

    assert any("src" in n for n in captured["DAG"].values())
    assert captured["rootNodeId"] == plain["rootNodeId"]
    assert list(captured["DAG"]) == list(plain["DAG"])
    assert json.dumps(_strip_source(captured), sort_keys=True) == json.dumps(
        plain, sort_keys=True
    )


def test_capture_off_emits_no_source_keys(project):
    assert not source_capture.is_enabled()
    for dag in (_build(project), _build(project, with_source=True)):
        assert all(
            key not in node for node in dag["DAG"].values() for key in SOURCE_NODE_KEYS
        )

    # Captured, but not asked for.
    with source_capture.capturing():
        dag = _build(project, with_source=False)
    assert all(
        key not in node for node in dag["DAG"].values() for key in SOURCE_NODE_KEYS
    )


@needs_columns
def test_exec_with_real_filename_and_non_ascii_columns(tmp_path, monkeypatch, capture):
    source = textwrap.dedent("""\
        from cadbuildr.foundation import Part, Sketch, Square, Extrusion

        class P(Part):
            def __init__(self):
                sq = Square.from_center_and_side(Sketch(self.xy()).origin, 4)
                é = "é"; self.add_operation(Extrusion(sq, 3))

        part = P()
        """)
    path = tmp_path / "sub" / "accent.py"
    path.parent.mkdir()
    path.write_text(source, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    namespace: dict = {"__name__": "__main__"}
    exec(compile(source, str(path), "exec"), namespace)
    dag = show_dag(namespace["part"])

    node = _extrusion_with_end_text(dag, "3")
    assert node["src"]["file"] == "sub/accent.py"
    _assert_ref_points_at_text(node["fieldSrc"]["end"], source)
    _assert_ref_points_at_text(node["src"], source)


def test_capture_failure_never_raises(project, capture, monkeypatch):
    def boom(frame):
        raise RuntimeError("boom")

    monkeypatch.setattr(source_capture, "_build_site", boom)
    monkeypatch.setattr(source_capture, "_SITE_CACHE", {})
    dag = _build(project)
    assert all("src" not in n for n in _nodes_of(dag, "Extrusion"))


def test_env_var_enables_capture_at_import():
    env = dict(os.environ, **{source_capture.ENV_VAR: "1"})
    out = subprocess.run(
        [
            sys.executable,
            "-c",
            "import cadbuildr.foundation as f; print(f.source_capture.is_enabled())",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == "True"
