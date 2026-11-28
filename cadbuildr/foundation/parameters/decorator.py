"""``@cadbuildr_project`` — registers a build function as a parametric project."""

from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import Any, Callable

from cadbuildr.foundation.parameters.descriptors import ParameterDescriptor


@dataclass(frozen=True)
class CadbuildrProjectMetadata:
    project_id: str
    title: str
    description: str | None
    parameters: tuple[ParameterDescriptor, ...]
    func: Callable[..., Any]

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "project_id": self.project_id,
            "title": self.title,
            "parameters": [p.to_json() for p in self.parameters],
        }
        if self.description is not None:
            out["description"] = self.description
        return out


# Module-level registry of every decorated function. Populated as modules
# import. The emit CLI walks this to write parameters.schema.json files.
CADBUILDR_PROJECT_REGISTRY: dict[str, CadbuildrProjectMetadata] = {}


def cadbuildr_project(
    *,
    project_id: str | None = None,
    title: str | None = None,
    description: str | None = None,
    parameters: list[ParameterDescriptor],
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator: marks ``func`` as a parametric CADbuildr project.

    Example::

        from cadbuildr.foundation import cadbuildr_project, Int, Color

        @cadbuildr_project(
            title="Single LEGO brick",
            parameters=[
                Int("n_length", default=2, min=1, max=16),
                Color("brick_color", default="bright_red"),
            ],
        )
        def lego_brick(n_length: int, brick_color: str):
            return LegoBrick(n_length=n_length, n_width=n_length, color=brick_color)
    """
    _validate_unique_ids(parameters)

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        resolved_id = project_id or func.__name__
        resolved_title = title or _humanize(resolved_id)
        metadata = CadbuildrProjectMetadata(
            project_id=resolved_id,
            title=resolved_title,
            description=description or (func.__doc__.strip() if func.__doc__ else None),
            parameters=tuple(parameters),
            func=func,
        )
        if resolved_id in CADBUILDR_PROJECT_REGISTRY:
            existing = CADBUILDR_PROJECT_REGISTRY[resolved_id]
            if existing.func is not func and not _same_definition(existing.func, func):
                raise ValueError(
                    f"Duplicate cadbuildr_project id {resolved_id!r}: "
                    f"{_where(existing.func)} vs {_where(func)}",
                )
        # Same function defined again (re-run of edited code in Pyodide or
        # Jupyter, importlib.reload, one file imported under two module names):
        # the newest definition wins.
        CADBUILDR_PROJECT_REGISTRY[resolved_id] = metadata
        _register_library_item(metadata)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        wrapper.__cadbuildr_parameters__ = metadata  # type: ignore[attr-defined]
        return wrapper

    return decorator


def descriptor_widget(p: ParameterDescriptor) -> dict[str, Any]:
    """A parameter descriptor as a library widget (``cadbuildr.foundation.library``)."""
    data = p.to_json()
    kind = data["type"]
    if kind in ("int", "float"):
        w: dict[str, Any] = {
            "kind": "number",
            "integer": kind == "int",
            "default": p.default,
        }
        for key in ("min", "max", "step"):
            if data.get(key) is not None:
                w[key] = data[key]
        return w
    if kind == "bool":
        return {"kind": "bool", "default": bool(p.default)}
    if kind == "enum":
        return {
            "kind": "enum",
            "options": [str(c) for c in data["choices"]],
            "default": str(p.default),
        }
    if kind == "color":
        from cadbuildr.foundation.constants import DEFAULT_COLORS

        choices = list(data.get("choices") or DEFAULT_COLORS)
        if p.default not in choices:
            choices.insert(0, p.default)
        return {
            "kind": "enum",
            "options": choices,
            "default": p.default,
            "custom": "choices" not in data,
        }
    return {"kind": "text", "default": str(p.default)}


def _register_library_item(metadata: CadbuildrProjectMetadata) -> None:
    """``@cadbuildr_project`` is a thin alias: the project is also a library item."""
    try:
        from cadbuildr.foundation.library.registry import LibraryItem, register
    except Exception:  # pragma: no cover - partial install
        return
    func = metadata.func
    register(
        LibraryItem(
            kind="project",
            obj=func,
            module=func.__module__,
            cls=func.__qualname__,
            name=metadata.title,
            description=metadata.description,
            overrides={
                p.id: {
                    "widget": descriptor_widget(p),
                    **({"label": p.label} if p.label else {}),
                    **({"description": p.description} if p.description else {}),
                }
                for p in metadata.parameters
            },
            extra={"project_id": metadata.project_id},
            signature_of=func,
        )
    )


def _same_definition(a: Callable[..., Any], b: Callable[..., Any]) -> bool:
    """Is ``b`` a re-definition of ``a``: same qualified name, and the same
    module or the same source file?"""
    if getattr(a, "__qualname__", None) != getattr(b, "__qualname__", None):
        return False
    if getattr(a, "__module__", None) == getattr(b, "__module__", None):
        return True
    fa = getattr(getattr(a, "__code__", None), "co_filename", None)
    fb = getattr(getattr(b, "__code__", None), "co_filename", None)
    return fa is not None and fa == fb


def _where(func: Callable[..., Any]) -> str:
    return f"{getattr(func, '__module__', '?')}.{getattr(func, '__qualname__', '?')}"


def _validate_unique_ids(parameters: list[ParameterDescriptor]) -> None:
    seen: set[str] = set()
    for p in parameters:
        if p.id in seen:
            raise ValueError(f"Duplicate parameter id {p.id!r}")
        seen.add(p.id)


def _humanize(slug: str) -> str:
    return slug.replace("_", " ").replace("-", " ").strip().title()
