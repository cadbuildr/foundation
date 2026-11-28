"""Input type hints of library configurables and the widgets they map to.

A configurable declares each input once, as a constructor argument with a type
hint; :func:`widget_for` turns that hint (and the argument's default) into the
widget dict the viewer's schema form renders (the ``Widget`` kinds of
``schema-driven-wizard`` ``createForm/model.ts``)::

    OneOf[TABLE] / Literal[...] / Enum   -> {"kind": "enum", "options", "default"}
    float / Num(min, max, step, unit)    -> {"kind": "number", "integer": False, "default", "unit"}
    int                                  -> {"kind": "number", "integer": True, "default"}
    bool                                 -> {"kind": "bool", "default"}
    str                                  -> {"kind": "text", "default"}
    Color                                -> {"kind": "enum", "options": named colours, "custom": True}
    a dataclass                          -> {"kind": "object", "type", "fields": [...]}
    InputOf[Cls, "input"]                -> the referenced input's widget
    a Part / Assembly / site class       -> {"kind": "existing", "type", "lookup"}
"""

from __future__ import annotations

import dataclasses
import enum
import inspect
import re
import sys
import types
import typing
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "Color",
    "InputOf",
    "InputOfSpec",
    "Num",
    "OneOf",
    "OneOfSpec",
    "evaluate_annotation",
    "humanize",
    "widget_for",
]


_EMPTY = inspect.Parameter.empty


# --------------------------------------------------------------------------- #
# Hint vocabulary
# --------------------------------------------------------------------------- #


class OneOfSpec:
    """The options of an ``OneOf[...]`` hint: a table's keys, in order, or a list."""

    def __init__(self, options: Any) -> None:
        self.table: Optional[Dict[Any, Any]] = None
        if isinstance(options, dict):
            self.table = options
            values = list(options.keys())
        elif isinstance(options, type) and issubclass(options, enum.Enum):
            values = list(options)
        elif isinstance(options, (list, tuple, set, frozenset, range)) or hasattr(
            options, "keys"
        ):
            values = list(options.keys()) if hasattr(options, "keys") else list(options)
        else:
            raise TypeError(
                f"OneOf[...] takes a table (dict) or a list, got {options!r}"
            )
        if not values:
            raise ValueError("OneOf[...] needs at least one option")
        self.values: List[Any] = values

    def labels(self) -> List[str]:
        return [_option_label(v) for v in self.values]

    def coerce(self, value: Any) -> Any:
        """The option a widget value (always a string) stands for."""
        if any(
            value is v or (type(value) is type(v) and value == v) for v in self.values
        ):
            return value
        for v in self.values:
            if _option_label(v) == str(value):
                return v
        return value

    def __repr__(self) -> str:
        return f"OneOf[{self.values!r}]"


class OneOf:
    """``model: OneOf[TABLE] = "608"`` — one key of a table (or one item of a list).

    The table rows also become the configurable's named configurations.
    """

    def __class_getitem__(cls, options: Any) -> OneOfSpec:
        return OneOfSpec(options)


class Num:
    """A number input with bounds and a unit: ``length: Num(min=3, max=80) = 20``.

    Used bare (``diameter: Num = 54``) it is a float in millimetres.
    """

    def __init__(
        self,
        min: Optional[float] = None,
        max: Optional[float] = None,
        step: Optional[float] = None,
        unit: Optional[str] = "mm",
        integer: bool = False,
        label: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        self.min = min
        self.max = max
        self.step = step
        self.unit = unit
        self.integer = integer
        self.label = label
        self.description = description

    def __repr__(self) -> str:
        parts = [
            f"{k}={v!r}"
            for k, v in (
                ("min", self.min),
                ("max", self.max),
                ("step", self.step),
                ("unit", self.unit),
            )
            if v is not None
        ]
        return f"Num({', '.join(parts)})"


class InputOfSpec:
    def __init__(self, cls: Any, input_name: str) -> None:
        self.cls = cls
        self.input_name = input_name

    def __repr__(self) -> str:
        return (
            f"InputOf[{getattr(self.cls, '__name__', self.cls)}, {self.input_name!r}]"
        )


class InputOf:
    """``bearing: InputOf[DeepGrooveBearing, "model"] = "608"`` — an input that
    takes the same values as another configurable's input (same widget)."""

    def __class_getitem__(cls, item: Tuple[Any, str]) -> InputOfSpec:
        if not isinstance(item, tuple) or len(item) != 2:
            raise TypeError('InputOf takes [Cls, "input_name"]')
        return InputOfSpec(item[0], item[1])


class Color(str):
    """A colour input: a named colour (``"red"``) or a hex string."""


# --------------------------------------------------------------------------- #
# Annotation evaluation
# --------------------------------------------------------------------------- #


def evaluate_annotation(annotation: Any, func: Any, owner: Any = None) -> Any:
    """Evaluate a string annotation (``from __future__ import annotations``) in
    the function's module, with the owning class body's names visible (so
    ``OneOf[TABLE]`` finds a class-level ``TABLE``)."""
    if not isinstance(annotation, str):
        return annotation
    module = sys.modules.get(getattr(func, "__module__", "") or "")
    globalns = dict(vars(module)) if module is not None else {}
    globalns.update(getattr(func, "__globals__", {}) or {})
    localns: Dict[str, Any] = {}
    if owner is not None:
        for klass in reversed(getattr(owner, "__mro__", (owner,))):
            localns.update(vars(klass))
        localns.setdefault(owner.__name__, owner)
    try:
        return eval(
            annotation, globalns, localns
        )  # noqa: S307 - the module's own annotation
    except Exception:
        return _EMPTY


# --------------------------------------------------------------------------- #
# Widgets
# --------------------------------------------------------------------------- #


def humanize(name: str) -> str:
    """``bore_seat`` -> ``Bore seat`` (same rule as the TS ``formLabel``)."""
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    s = re.sub(r"([a-zA-Z])([0-9])", r"\1 \2", s)
    s = s.replace("_", " ").strip().lower()
    return s[:1].upper() + s[1:]


def _option_label(value: Any) -> str:
    if isinstance(value, enum.Enum):
        return value.name
    return str(value)


def _is_optional(hint: Any) -> Tuple[bool, Any]:
    origin = typing.get_origin(hint)
    union_types = (typing.Union,) + (
        (types.UnionType,) if hasattr(types, "UnionType") else ()
    )
    if origin in union_types:
        args = [a for a in typing.get_args(hint) if a is not type(None)]
        if len(args) == 1 and len(typing.get_args(hint)) == 2:
            return True, args[0]
    return False, hint


def _number_default(default: Any, integer: bool) -> Any:
    if default is _EMPTY or isinstance(default, bool):
        return 0
    if isinstance(default, (int, float)):
        return int(default) if integer else default
    return default


def _part_like(hint: Any) -> bool:
    try:
        from ..gen.models import Assembly, Part

        return isinstance(hint, type) and issubclass(hint, (Part, Assembly))
    except Exception:  # pragma: no cover
        return False


def widget_for(hint: Any, default: Any = _EMPTY, owner: Any = None) -> Dict[str, Any]:
    """The widget dict for one input (see the module docstring)."""
    # Annotated[T, spec]: our specs travel as metadata.
    if typing.get_origin(hint) is typing.Annotated:
        base, *meta = typing.get_args(hint)
        for m in meta:
            if isinstance(m, (OneOfSpec, Num, InputOfSpec)) or m is Num:
                return widget_for(m, default, owner)
        hint = base

    optional, hint = _is_optional(hint)
    widget = _widget(hint, default, owner)
    if optional or default is None:
        widget["optional"] = True
        if default is None:
            widget["default"] = None
    return widget


def _widget(hint: Any, default: Any, owner: Any) -> Dict[str, Any]:
    if isinstance(hint, OneOfSpec):
        options = hint.labels()
        d = _option_label(default) if default not in (_EMPTY, None) else options[0]
        return {"kind": "enum", "options": options, "default": d}
    if isinstance(hint, InputOfSpec):
        return _input_of_widget(hint, default)
    if hint is Num or isinstance(hint, Num):
        spec = hint if isinstance(hint, Num) else Num()
        w: Dict[str, Any] = {
            "kind": "number",
            "integer": bool(spec.integer),
            "default": _number_default(default, spec.integer),
        }
        if spec.unit:
            w["unit"] = spec.unit
        for key in ("min", "max", "step"):
            value = getattr(spec, key)
            if value is not None:
                w[key] = value
        return w
    if typing.get_origin(hint) is typing.Literal:
        spec = OneOfSpec(list(typing.get_args(hint)))
        return _widget(spec, default, owner)
    if isinstance(hint, type) and issubclass(hint, enum.Enum):
        return _widget(OneOfSpec(hint), default, owner)
    if hint is Color:
        from ..constants import DEFAULT_COLORS

        options = list(DEFAULT_COLORS)
        d = default if isinstance(default, str) else options[0]
        if d not in options:
            options = [d] + options
        return {"kind": "enum", "options": options, "default": d, "custom": True}
    if hint is bool:
        return {
            "kind": "bool",
            "default": bool(default) if default is not _EMPTY else False,
        }
    if hint is int:
        return {
            "kind": "number",
            "integer": True,
            "default": _number_default(default, True),
        }
    if hint is float:
        return {
            "kind": "number",
            "integer": False,
            "default": _number_default(default, False),
            "unit": "mm",
        }
    if hint is str:
        return {"kind": "text", "default": default if isinstance(default, str) else ""}
    if isinstance(hint, type) and dataclasses.is_dataclass(hint):
        return _dataclass_widget(hint)
    if hint is _EMPTY or hint is Any or hint is None:
        # No usable hint: infer from the default's type.
        if isinstance(default, bool):
            return _widget(bool, default, owner)
        if isinstance(default, int):
            return _widget(int, default, owner)
        if isinstance(default, float):
            return _widget(float, default, owner)
        if isinstance(default, str):
            return _widget(str, default, owner)
        if isinstance(default, enum.Enum):
            return _widget(type(default), default, owner)
        if dataclasses.is_dataclass(default) and not isinstance(default, type):
            return _dataclass_widget(type(default))
        return {"kind": "existing", "type": "Any", "lookup": "pick"}
    if _part_like(hint) or (isinstance(hint, type) and hint.__module__ != "builtins"):
        return {"kind": "existing", "type": hint.__name__, "lookup": "pick"}
    # Generic aliases (list[float], tuple...) have no widget yet: free text.
    return {
        "kind": "text",
        "default": "" if default in (_EMPTY, None) else repr(default),
    }


def _input_of_widget(spec: InputOfSpec, default: Any) -> Dict[str, Any]:
    from .registry import item_for

    item = item_for(spec.cls)
    if item is None:
        raise TypeError(f"{spec!r}: {spec.cls!r} is not a library configurable")
    target = item.input(spec.input_name)
    if target is None:
        raise TypeError(f"{spec!r}: {item.cls} has no input {spec.input_name!r}")
    widget = dict(target["widget"])
    if default is not _EMPTY:
        widget["default"] = (
            _option_label(default) if widget["kind"] == "enum" else default
        )
    widget["inputOf"] = {"item": item.id, "input": spec.input_name}
    return widget


def _dataclass_widget(cls: type) -> Dict[str, Any]:
    try:
        hints = typing.get_type_hints(cls)
    except Exception:
        hints = {}
    fields = []
    for f in dataclasses.fields(cls):
        if f.default is not dataclasses.MISSING:
            default = f.default
        elif f.default_factory is not dataclasses.MISSING:  # type: ignore[misc]
            default = f.default_factory()  # type: ignore[misc]
        else:
            default = _EMPTY
        hint = hints.get(f.name, f.type)
        if isinstance(hint, str):
            hint = evaluate_annotation(hint, cls, None)
        fields.append(
            {
                "name": f.name,
                "label": humanize(f.name),
                "widget": widget_for(hint, default),
                "required": default is _EMPTY,
                "hasDefault": default is not _EMPTY,
            }
        )
    return {"kind": "object", "type": cls.__name__, "fields": fields}


def coerce_value(widget: Dict[str, Any], hint: Any, value: Any) -> Any:
    """Turn a widget value (JSON) back into what the constructor expects."""
    if value is None:
        return None
    if typing.get_origin(hint) is typing.Annotated:
        for m in typing.get_args(hint)[1:]:
            if isinstance(m, (OneOfSpec, Num, InputOfSpec)):
                hint = m
                break
    _, hint = _is_optional(hint)
    if isinstance(hint, InputOfSpec):
        from .registry import item_for

        item = item_for(hint.cls)
        target = item.parameter_hint(hint.input_name) if item else _EMPTY
        return coerce_value(widget, target, value)
    if isinstance(hint, OneOfSpec):
        return hint.coerce(value)
    if typing.get_origin(hint) is typing.Literal:
        return OneOfSpec(list(typing.get_args(hint))).coerce(value)
    if isinstance(hint, type) and issubclass(hint, enum.Enum):
        if isinstance(value, hint):
            return value
        try:
            return hint[value]
        except KeyError:
            return hint(value)
    if (
        isinstance(hint, type)
        and dataclasses.is_dataclass(hint)
        and isinstance(value, dict)
    ):
        return hint(**value)
    kind = widget.get("kind")
    if (
        kind == "number"
        and isinstance(value, (int, float, str))
        and not isinstance(value, bool)
    ):
        number = float(value)
        if widget.get("integer"):
            return int(round(number))
        return int(number) if isinstance(value, int) else number
    if kind == "bool" and isinstance(value, str):
        return value.lower() in ("1", "true", "yes", "on")
    return value
