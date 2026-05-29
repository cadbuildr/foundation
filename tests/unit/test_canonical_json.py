"""Cross-language fixture tests for canonical JSON serialization.

These fixtures are shared with the TS-side canonicalJson tests; both sides
must produce byte-identical output. The fixture file lives in the TS package
because Jest resolves paths relative to the TS workspace; we reach across to
read the same JSON here.
"""

import json
from pathlib import Path

import pytest

from cadbuildr.foundation.gen.dag.canonical_json import serialize


_FIXTURE_PATH = (
    Path(__file__).resolve().parents[6]
    / "tsjs/packages/dag/dag-utils/__test__/fixtures/canonical-json/cases.json"
)


def _load_cases() -> dict:
    with _FIXTURE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize("name,case", list(_load_cases().items()))
def test_canonical_json_matches_fixture(name: str, case: dict) -> None:
    assert serialize(case["input"]) == case["expected"], (
        f"canonical_json drift for fixture {name!r}"
    )


def test_double_quote_and_backslash_escapes() -> None:
    assert serialize({"s": 'he said "hi"'}) == '{"s": "he said \\"hi\\""}'
    assert serialize({"s": "a\\b"}) == '{"s": "a\\\\b"}'


def test_array_order_is_preserved() -> None:
    assert serialize([3, 1, 2]) == "[3, 1, 2]"
