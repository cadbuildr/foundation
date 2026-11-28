"""@cadbuildr_project re-registration: re-running edited code (Pyodide,
Jupyter, importlib.reload) defines the same project function again and must
not raise; two different functions claiming one id still must."""

import types

import pytest

from cadbuildr.foundation import Int, cadbuildr_project
from cadbuildr.foundation.parameters.decorator import CADBUILDR_PROJECT_REGISTRY

SRC = """
from cadbuildr.foundation import Int, cadbuildr_project

@cadbuildr_project(project_id="redef_probe", parameters=[Int("n", default=%d)])
def puzzle_for_date(n):
    return n
"""


def _run(source, module_name, filename="<puzzle.py>"):
    mod = types.ModuleType(module_name)
    exec(compile(source, filename, "exec"), mod.__dict__)
    return mod


@pytest.fixture(autouse=True)
def _clean():
    CADBUILDR_PROJECT_REGISTRY.pop("redef_probe", None)
    CADBUILDR_PROJECT_REGISTRY.pop("redef_clash", None)
    yield
    CADBUILDR_PROJECT_REGISTRY.pop("redef_probe", None)
    CADBUILDR_PROJECT_REGISTRY.pop("redef_clash", None)


def test_rerunning_edited_code_replaces_the_project():
    _run(SRC % 1, "puzzle")
    _run(SRC % 2, "puzzle")  # same module, edited and re-run
    meta = CADBUILDR_PROJECT_REGISTRY["redef_probe"]
    assert meta.parameters[0].default == 2  # newest definition wins


def test_same_file_imported_under_two_module_names():
    _run(SRC % 1, "pkg.puzzle", filename="/src/puzzle.py")
    _run(SRC % 1, "puzzle", filename="/src/puzzle.py")
    assert "redef_probe" in CADBUILDR_PROJECT_REGISTRY


def test_different_projects_claiming_one_id_still_raise():
    @cadbuildr_project(project_id="redef_clash", parameters=[Int("n", default=1)])
    def first(n):
        return n

    with pytest.raises(
        ValueError, match="Duplicate cadbuildr_project id 'redef_clash'"
    ):

        @cadbuildr_project(project_id="redef_clash", parameters=[Int("n", default=1)])
        def second(n):
            return n
