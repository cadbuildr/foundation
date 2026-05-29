"""Tests for the ``@cadbuildr_project`` decorator + schema emit."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cadbuildr.foundation.parameters import (
    Bool,
    Color,
    Enum,
    Float,
    Int,
    cadbuildr_project,
)
from cadbuildr.foundation.parameters.decorator import CADBUILDR_PROJECT_REGISTRY
from cadbuildr.foundation.parameters.schema import (
    build_project_schema,
    emit_project_schema,
)


def _isolate_registry() -> None:
    """Pytest helper: drop entries the test owns so tests stay independent."""
    for k in list(CADBUILDR_PROJECT_REGISTRY):
        if k.startswith("_test_"):
            del CADBUILDR_PROJECT_REGISTRY[k]


def test_int_validation() -> None:
    Int("x", default=5, min=0, max=10, step=1)
    with pytest.raises(ValueError):
        Int("x", default=20, min=0, max=10)
    with pytest.raises(ValueError):
        Int("x", default=5, step=0)
    with pytest.raises(TypeError):
        Int("x", default="hi")  # type: ignore[arg-type]


def test_enum_default_must_be_in_choices() -> None:
    with pytest.raises(ValueError):
        Enum("x", default="z", choices=["a", "b"])


def test_decorator_registers_and_keeps_function_callable() -> None:
    _isolate_registry()

    @cadbuildr_project(
        project_id="_test_minimal",
        title="Minimal",
        parameters=[Int("n", default=2, min=1, max=4)],
    )
    def build(n: int) -> int:
        return n * 10

    assert build(3) == 30
    assert "_test_minimal" in CADBUILDR_PROJECT_REGISTRY
    metadata = CADBUILDR_PROJECT_REGISTRY["_test_minimal"]
    assert metadata.title == "Minimal"
    assert metadata.parameters[0].id == "n"
    _isolate_registry()


def test_duplicate_parameter_ids_rejected() -> None:
    _isolate_registry()
    with pytest.raises(ValueError):

        @cadbuildr_project(
            project_id="_test_dupe",
            parameters=[Int("n", default=1), Int("n", default=2)],
        )
        def build() -> None:
            pass

    _isolate_registry()


def test_full_schema_round_trip(tmp_path: Path) -> None:
    _isolate_registry()

    @cadbuildr_project(
        project_id="_test_full",
        title="Full sample",
        description="Doc string flowed in.",
        parameters=[
            Int("count", default=2, min=1, max=8, step=1, label="Count"),
            Float("ratio", default=1.5, min=0.5, max=4.0, step=0.5),
            Bool("hollow", default=False),
            Color("color", default="bright_red", choices=("bright_red", "blue")),
            Enum("style", default="solid", choices=("solid", "wire")),
        ],
    )
    def build(count: int, ratio: float, hollow: bool, color: str, style: str) -> int:
        return count

    metadata = CADBUILDR_PROJECT_REGISTRY["_test_full"]
    schema = build_project_schema(metadata)

    assert schema["project_id"] == "_test_full"
    assert schema["title"] == "Full sample"
    assert schema["description"] == "Doc string flowed in."
    assert [p["id"] for p in schema["parameters"]] == [
        "count",
        "ratio",
        "hollow",
        "color",
        "style",
    ]
    int_param = schema["parameters"][0]
    assert int_param == {
        "id": "count",
        "type": "int",
        "default": 2,
        "label": "Count",
        "min": 1,
        "max": 8,
        "step": 1,
    }
    float_param = schema["parameters"][1]
    assert float_param["type"] == "float"
    assert float_param["step"] == 0.5
    bool_param = schema["parameters"][2]
    assert bool_param == {"id": "hollow", "type": "bool", "default": False}
    color_param = schema["parameters"][3]
    assert color_param["choices"] == ["bright_red", "blue"]
    enum_param = schema["parameters"][4]
    assert enum_param["choices"] == ["solid", "wire"]

    target = tmp_path / "_test_full.schema.json"
    emit_project_schema(metadata, target)
    parsed = json.loads(target.read_text())
    assert parsed == schema
    _isolate_registry()


def test_duplicate_project_id_rejected() -> None:
    _isolate_registry()

    @cadbuildr_project(
        project_id="_test_dup_project",
        parameters=[Int("n", default=1)],
    )
    def build_a() -> None:
        pass

    with pytest.raises(ValueError):

        @cadbuildr_project(
            project_id="_test_dup_project",
            parameters=[Int("n", default=1)],
        )
        def build_b() -> None:
            pass

    _isolate_registry()
