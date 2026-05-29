"""Parameter schema decorators for CADbuildr projects.

A project author wraps a build function with ``@cadbuildr_project`` and lists
its tunable inputs as ``Int`` / ``Float`` / ``Bool`` / ``Color`` / ``Enum``
descriptors. At build time we emit a ``parameters.schema.json`` next to the
project so the SDK auto-form (T11) and the frozen-DAG substituter (T12) can
read the contract without invoking Python in the browser.
"""

from cadbuildr.foundation.parameters.descriptors import (
    Bool,
    Color,
    Enum,
    Float,
    Int,
    ParameterDescriptor,
)
from cadbuildr.foundation.parameters.decorator import (
    CADBUILDR_PROJECT_REGISTRY,
    CadbuildrProjectMetadata,
    cadbuildr_project,
)
from cadbuildr.foundation.parameters.schema import (
    ProjectSchema,
    build_project_schema,
    emit_project_schema,
    emit_schemas_for_module,
)

__all__ = [
    "Bool",
    "CADBUILDR_PROJECT_REGISTRY",
    "CadbuildrProjectMetadata",
    "Color",
    "Enum",
    "Float",
    "Int",
    "ParameterDescriptor",
    "ProjectSchema",
    "build_project_schema",
    "cadbuildr_project",
    "emit_project_schema",
    "emit_schemas_for_module",
]
