"""Canonical JSON serializer for cross-language hash parity.

The TS-side serializer in `tsjs/packages/dag/dag-utils/src/canonicalJson.ts` is
required to produce byte-identical output for the value subset we use in DAG
hashing. This module is the Python reference implementation; the fixture tests
in `tests/unit/test_canonical_json.py` run on both sides against the same JSON
inputs to detect drift.

Equivalent to ``json.dumps(value, sort_keys=True)`` with the CPython defaults:
separators ``(", ", ": ")``, ``ensure_ascii=True``.
"""

import json
from typing import Any


def serialize(value: Any) -> str:
    """Return the canonical JSON string for ``value``."""
    return json.dumps(value, sort_keys=True)
