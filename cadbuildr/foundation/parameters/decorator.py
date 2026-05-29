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
            if existing.func is not func:
                raise ValueError(
                    f"Duplicate cadbuildr_project id {resolved_id!r}: "
                    f"{existing.func.__qualname__} vs {func.__qualname__}",
                )
        CADBUILDR_PROJECT_REGISTRY[resolved_id] = metadata

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        wrapper.__cadbuildr_parameters__ = metadata  # type: ignore[attr-defined]
        return wrapper

    return decorator


def _validate_unique_ids(parameters: list[ParameterDescriptor]) -> None:
    seen: set[str] = set()
    for p in parameters:
        if p.id in seen:
            raise ValueError(f"Duplicate parameter id {p.id!r}")
        seen.add(p.id)


def _humanize(slug: str) -> str:
    return slug.replace("_", " ").replace("-", " ").strip().title()
