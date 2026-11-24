"""ImportStep reads a STEP file like open() does and carries its text in the DAG."""

import hashlib
import io
import pathlib

import pytest

from cadbuildr.foundation import (
    Fillet,
    ImportStep,
    MoveBody,
    Part,
    Point3D,
    StepFileError,
)
from cadbuildr.foundation.dag_utils import show_dag

STEP = (
    "ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION(('a box'),'2;1');\nENDSEC;\n"
    "DATA;\n#1 = CARTESIAN_POINT('',(0.,0.,0.));\nENDSEC;\nEND-ISO-10303-21;\n"
)


@pytest.fixture
def step_file(tmp_path):
    path = tmp_path / "nema17.step"
    path.write_text(STEP)
    return path


def test_reads_a_path_like_open(step_file):
    step = ImportStep(str(step_file))
    assert step.content.value == STEP
    assert step.filename.value == "nema17.step"
    assert step.sha256.value == hashlib.sha256(STEP.encode()).hexdigest()
    assert step.cut.value is False


def test_accepts_pathlike(step_file):
    assert ImportStep(pathlib.Path(step_file)).content.value == STEP


def test_relative_path_resolves_from_cwd(step_file, monkeypatch):
    monkeypatch.chdir(step_file.parent)
    assert ImportStep("nema17.step").filename.value == "nema17.step"


def test_missing_file_names_path_and_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError, match=r"missing\.step.*current directory"):
        ImportStep("missing.step")


def test_open_text_and_binary_files(step_file):
    with open(step_file) as f:
        assert ImportStep(f).filename.value == "nema17.step"
    with open(step_file, "rb") as f:
        assert ImportStep(f).content.value == STEP
    # Any object with .read() works; without a name it is labelled inline.
    assert ImportStep(io.StringIO(STEP)).filename.value == "inline.step"
    assert ImportStep(io.BytesIO(STEP.encode())).content.value == STEP


def test_from_text():
    step = ImportStep.from_text(STEP, "motor.step")
    assert step.filename.value == "motor.step"
    assert ImportStep.from_text(STEP).filename.value == "inline.step"


def test_cut_flag(step_file):
    assert ImportStep(step_file, cut=True).cut.value is True


@pytest.mark.parametrize(
    "text, match",
    [
        ("", "empty"),
        ("solid cube\nfacet normal 0 0 1\n", "not a STEP file"),
        ("ISO-10303-21;\nHEADER;\nENDSEC;\n", "missing its HEADER or DATA"),
    ],
)
def test_rejects_non_step_text(tmp_path, text, match):
    path = tmp_path / "bad.stl"
    path.write_text(text)
    with pytest.raises(StepFileError, match=rf"bad\.stl: .*{match}"):
        ImportStep(path)
    with pytest.raises(StepFileError, match=match):
        ImportStep.from_text(text)


def test_step_text_passed_as_path_points_to_from_text():
    with pytest.raises(StepFileError, match="from_text"):
        ImportStep(STEP)


def test_needs_a_source():
    with pytest.raises(TypeError, match="needs a STEP file"):
        ImportStep()
    with pytest.raises(TypeError, match="path"):
        ImportStep(42)


def test_part_from_step_and_dag(step_file):
    part = Part.from_step(step_file)
    assert part.name.value == "nema17"
    (op,) = part.operations
    assert isinstance(op, ImportStep)
    dag = show_dag(part)
    # The file's text travels in the DAG: no path, no storage reference.
    step_type = dag["serializableNodes"]["ImportStep"]
    (node,) = [n for n in dag["DAG"].values() if n["type"] == step_type]
    assert dag["DAG"][node["deps"]["content"]]["params"]["value"] == STEP
    assert dag["DAG"][node["deps"]["filename"]]["params"]["value"] == "nema17.step"


def test_is_a_solid_operation(step_file):
    step = ImportStep(step_file)
    Fillet(solid=step, radius=1.0)
    MoveBody(step, Point3D(1.0, 2.0, 3.0))


def test_extents_are_unknown_unless_declared(step_file):
    from cadbuildr.foundation import estimate_part_extents

    part = Part.from_step(step_file)
    extents = estimate_part_extents(part)
    assert any("ImportStep 'nema17.step'" in reason for reason in extents.unknown)
    part.set_extents(((0, 0, 0), (42, 42, 48)))
    assert not estimate_part_extents(part).unknown
