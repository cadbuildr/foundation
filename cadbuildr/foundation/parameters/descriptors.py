"""Typed parameter descriptors emitted into ``parameters.schema.json``.

Each descriptor produces a JSON object the SDK auto-form (T11) consumes:
sliders for ``Int`` / ``Float``, dropdowns for ``Enum``, toggles for ``Bool``,
swatches for ``Color``. Step sizes flow into the cache-key discretization
policy (parent doc, section "Cache discretization").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ParameterDescriptor:
    """Base shape; subclasses set ``type`` and add type-specific fields."""

    id: str
    type: str
    default: Any
    label: str | None = None
    description: str | None = None

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {"id": self.id, "type": self.type, "default": self.default}
        if self.label is not None:
            out["label"] = self.label
        if self.description is not None:
            out["description"] = self.description
        return out


@dataclass(frozen=True)
class Int(ParameterDescriptor):
    type: str = "int"
    default: int = 0
    min: int | None = None
    max: int | None = None
    step: int = 1

    def __init__(  # noqa: PLR0913 - parameter descriptors are inherently wide
        self,
        id: str,
        *,
        default: int,
        min: int | None = None,
        max: int | None = None,
        step: int = 1,
        label: str | None = None,
        description: str | None = None,
    ) -> None:
        object.__setattr__(self, "id", id)
        object.__setattr__(self, "type", "int")
        object.__setattr__(self, "default", default)
        object.__setattr__(self, "min", min)
        object.__setattr__(self, "max", max)
        object.__setattr__(self, "step", step)
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "description", description)
        _validate_int(self)

    def to_json(self) -> dict[str, Any]:
        out = super().to_json()
        if self.min is not None:
            out["min"] = self.min
        if self.max is not None:
            out["max"] = self.max
        out["step"] = self.step
        return out


@dataclass(frozen=True)
class Float(ParameterDescriptor):
    type: str = "float"
    default: float = 0.0
    min: float | None = None
    max: float | None = None
    step: float = 0.1

    def __init__(  # noqa: PLR0913
        self,
        id: str,
        *,
        default: float,
        min: float | None = None,
        max: float | None = None,
        step: float = 0.1,
        label: str | None = None,
        description: str | None = None,
    ) -> None:
        object.__setattr__(self, "id", id)
        object.__setattr__(self, "type", "float")
        object.__setattr__(self, "default", default)
        object.__setattr__(self, "min", min)
        object.__setattr__(self, "max", max)
        object.__setattr__(self, "step", step)
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "description", description)
        _validate_float(self)

    def to_json(self) -> dict[str, Any]:
        out = super().to_json()
        if self.min is not None:
            out["min"] = self.min
        if self.max is not None:
            out["max"] = self.max
        out["step"] = self.step
        return out


@dataclass(frozen=True)
class Bool(ParameterDescriptor):
    type: str = "bool"
    default: bool = False

    def __init__(
        self,
        id: str,
        *,
        default: bool,
        label: str | None = None,
        description: str | None = None,
    ) -> None:
        object.__setattr__(self, "id", id)
        object.__setattr__(self, "type", "bool")
        object.__setattr__(self, "default", default)
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "description", description)


@dataclass(frozen=True)
class Color(ParameterDescriptor):
    type: str = "color"
    default: str = ""
    choices: tuple[str, ...] | None = None

    def __init__(
        self,
        id: str,
        *,
        default: str,
        choices: tuple[str, ...] | list[str] | None = None,
        label: str | None = None,
        description: str | None = None,
    ) -> None:
        object.__setattr__(self, "id", id)
        object.__setattr__(self, "type", "color")
        object.__setattr__(self, "default", default)
        object.__setattr__(self, "choices", tuple(choices) if choices is not None else None)
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "description", description)

    def to_json(self) -> dict[str, Any]:
        out = super().to_json()
        if self.choices is not None:
            out["choices"] = list(self.choices)
        return out


@dataclass(frozen=True)
class Enum(ParameterDescriptor):
    type: str = "enum"
    default: str = ""
    choices: tuple[str, ...] = field(default_factory=tuple)

    def __init__(
        self,
        id: str,
        *,
        default: str,
        choices: tuple[str, ...] | list[str],
        label: str | None = None,
        description: str | None = None,
    ) -> None:
        object.__setattr__(self, "id", id)
        object.__setattr__(self, "type", "enum")
        object.__setattr__(self, "default", default)
        object.__setattr__(self, "choices", tuple(choices))
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "description", description)
        if default not in self.choices:
            raise ValueError(
                f"Enum parameter {id!r}: default {default!r} not in choices {list(self.choices)!r}",
            )

    def to_json(self) -> dict[str, Any]:
        out = super().to_json()
        out["choices"] = list(self.choices)
        return out


def _validate_int(p: Int) -> None:
    if not isinstance(p.default, int) or isinstance(p.default, bool):
        raise TypeError(f"Int parameter {p.id!r} default must be int, got {type(p.default).__name__}")
    if p.min is not None and p.default < p.min:
        raise ValueError(f"Int parameter {p.id!r} default {p.default} < min {p.min}")
    if p.max is not None and p.default > p.max:
        raise ValueError(f"Int parameter {p.id!r} default {p.default} > max {p.max}")
    if p.step <= 0:
        raise ValueError(f"Int parameter {p.id!r} step must be positive, got {p.step}")


def _validate_float(p: Float) -> None:
    if not isinstance(p.default, (int, float)) or isinstance(p.default, bool):
        raise TypeError(f"Float parameter {p.id!r} default must be a number")
    if p.min is not None and p.default < p.min:
        raise ValueError(f"Float parameter {p.id!r} default {p.default} < min {p.min}")
    if p.max is not None and p.default > p.max:
        raise ValueError(f"Float parameter {p.id!r} default {p.default} > max {p.max}")
    if p.step <= 0:
        raise ValueError(f"Float parameter {p.id!r} step must be positive, got {p.step}")
