"""Emit ``parameters.schema.json`` for decorated projects."""

from __future__ import annotations

import importlib
import importlib.util
import json
import pkgutil
from pathlib import Path
from types import ModuleType
from typing import Any

from cadbuildr.foundation.parameters.decorator import (
    CADBUILDR_PROJECT_REGISTRY,
    CadbuildrProjectMetadata,
)

ProjectSchema = dict[str, Any]


def build_project_schema(metadata: CadbuildrProjectMetadata) -> ProjectSchema:
    return metadata.to_json()


def emit_project_schema(metadata: CadbuildrProjectMetadata, output_path: Path) -> Path:
    """Write a single project schema as deterministic JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    schema = build_project_schema(metadata)
    output_path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    return output_path


def _walk_module_tree(module: ModuleType) -> list[ModuleType]:
    """Import every submodule of ``module`` so the decorator side-effects run."""
    modules = [module]
    if not hasattr(module, "__path__"):
        return modules
    for info in pkgutil.walk_packages(module.__path__, prefix=f"{module.__name__}."):
        try:
            modules.append(importlib.import_module(info.name))
        except Exception as exc:  # pragma: no cover - defensive; log to stderr
            print(f"warning: failed to import {info.name}: {exc}")
    return modules


def emit_schemas_for_module(
    module_name: str,
    output_dir: Path,
) -> list[Path]:
    """Import ``module_name`` (and its submodules), then emit every registered
    project's schema into ``output_dir`` as ``<project_id>.schema.json``.

    Returns the list of written file paths in registration order.
    """
    module = importlib.import_module(module_name)
    _walk_module_tree(module)

    output_dir = Path(output_dir)
    written: list[Path] = []
    for project_id, metadata in CADBUILDR_PROJECT_REGISTRY.items():
        qualified = getattr(metadata.func, "__module__", "")
        if not (qualified == module_name or qualified.startswith(module_name + ".")):
            continue
        target = output_dir / f"{project_id}.schema.json"
        emit_project_schema(metadata, target)
        written.append(target)
    return written
