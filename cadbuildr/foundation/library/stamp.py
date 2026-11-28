"""``library_ref`` stamping: what a decorated constructor was called with.

``@part`` / ``@assembly`` wrap the class's ``__init__``. Each call records its
bound arguments (defaults included), the configuration they match, the
bindings to the enclosing configurable's inputs, and the library source that
was loaded; the record becomes a ``LibraryRef`` on the instance, which
``_convert_component_to_root`` copies onto the PartRoot / AssemblyRoot.

Bindings: while a decorated ``__init__`` runs, its inputs sit on a call stack.
A decorated child built inside it with an argument that comes from one of those
inputs is *bound* to it: the argument is written as the parent input's name
(``DeepGrooveBearing(model=bearing)`` / ``model=self.bearing``), or is the very
same object as the parent's value and is not written as a literal.
"""

from __future__ import annotations

import ast
import inspect
import json
import sys
import threading
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

from .registry import LibraryItem, _to_json

__all__ = ["current_stack", "install", "suspended", "stamp_of"]

_LIBRARY_REF_ATTR = "_library_ref"
_STAMP_ATTR = "_library_stamp"

_local = threading.local()


class _Call:
    __slots__ = ("item", "inputs", "self_obj")

    def __init__(
        self, item: LibraryItem, inputs: Dict[str, Any], self_obj: Any
    ) -> None:
        self.item = item
        self.inputs = inputs
        self.self_obj = self_obj


def _stack() -> List[_Call]:
    stack = getattr(_local, "stack", None)
    if stack is None:
        stack = _local.stack = []
    return stack


def current_stack() -> List[_Call]:
    return list(_stack())


def _suspended_depth() -> int:
    return getattr(_local, "suspended", 0)


@contextmanager
def suspended() -> Iterator[None]:
    """Build without stamping (manifest anchor probes)."""
    _local.suspended = _suspended_depth() + 1
    try:
        yield
    finally:
        _local.suspended = _suspended_depth() - 1


# --------------------------------------------------------------------------- #
# Wrapping
# --------------------------------------------------------------------------- #


def install(cls: type, item: LibraryItem) -> None:
    """Wrap ``cls.__init__`` so instances of exactly ``cls`` get stamped."""
    init = cls.__dict__.get("__init__")
    inherited = init is None
    if inherited:
        init = cls.__init__
    if getattr(init, "__library_stamp__", None) is cls:
        return
    try:
        signature = inspect.signature(item.signature_of)
    except (TypeError, ValueError):
        signature = None

    def __init__(self: Any, *args: Any, **kwargs: Any) -> None:
        if type(self) is not cls or _suspended_depth() or signature is None:
            init(self, *args, **kwargs)
            return
        try:
            bound = signature.bind(self, *args, **kwargs)
            bound.apply_defaults()
        except TypeError:
            init(self, *args, **kwargs)  # let the real constructor raise
            return
        inputs = _flatten(signature, bound.arguments)
        bindings = _bindings(inputs, args, kwargs, signature, sys._getframe(1))
        stack = _stack()
        stack.append(_Call(item, inputs, self))
        try:
            init(self, *args, **kwargs)
        finally:
            stack.pop()
        try:
            _stamp(self, item, inputs, bindings)
        except Exception:
            pass  # provenance never breaks a build

    __init__.__qualname__ = f"{cls.__qualname__}.__init__"
    __init__.__doc__ = getattr(init, "__doc__", None)
    __init__.__library_stamp__ = cls  # type: ignore[attr-defined]
    __init__.__foundation_auto_init__ = True  # type: ignore[attr-defined]
    __init__.__foundation_original_init__ = item.signature_of  # type: ignore[attr-defined]
    cls.__init__ = __init__  # type: ignore[misc]


def _flatten(signature: inspect.Signature, arguments: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for i, (name, value) in enumerate(arguments.items()):
        if i == 0 and name == "self":
            continue
        param = signature.parameters.get(name)
        if param is not None and param.kind is inspect.Parameter.VAR_KEYWORD:
            out.update(value)
        elif param is not None and param.kind is inspect.Parameter.VAR_POSITIONAL:
            continue
        else:
            out[name] = value
    return out


# --------------------------------------------------------------------------- #
# Bindings
# --------------------------------------------------------------------------- #

_LITERAL = object()


def _arg_texts(
    frame: Any, signature: inspect.Signature, n_positional: int
) -> Optional[Dict[str, Any]]:
    """{parameter: ast node} for the arguments written at the call in ``frame``."""
    try:
        from ..source_capture import _build_site

        site = _build_site(frame)
    except Exception:
        return None
    if not site.positional and not site.keywords:
        return None
    params = [p for p in signature.parameters.values()][1:]  # drop self
    out: Dict[str, Any] = {}
    if site.complete and len(site.positional) == n_positional:
        for param, ref in zip(params, site.positional):
            if ref is not None and "text" in ref:
                out[param.name] = ref["text"]
    for name, ref in site.keywords.items():
        if "text" in ref:
            out[name] = ref["text"]
    return out


def _written_name(text: str) -> Any:
    """``bearing`` / ``self.bearing`` -> "bearing"; a literal -> _LITERAL; else None."""
    try:
        node = ast.parse(text.strip(), mode="eval").body
    except SyntaxError:
        return None
    if isinstance(node, ast.Name):
        return node.id
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    ):
        return node.attr
    try:
        ast.literal_eval(node)
        return _LITERAL
    except Exception:
        return None


def _same(a: Any, b: Any) -> bool:
    if a is b:
        return True
    try:
        return type(a) is type(b) and bool(a == b)
    except Exception:
        return False


def _bindings(
    inputs: Dict[str, Any],
    args: tuple,
    kwargs: Dict[str, Any],
    signature: inspect.Signature,
    frame: Any,
) -> Dict[str, str]:
    stack = _stack()
    if not stack:
        return {}
    parent = stack[-1]
    params = [p.name for p in list(signature.parameters.values())[1:]]
    explicit = set(params[: len(args)]) | set(kwargs)
    if not explicit:
        return {}
    texts = _arg_texts(frame, signature, len(args)) or {}
    out: Dict[str, str] = {}
    for name in explicit:
        if name not in inputs:
            continue
        value = inputs[name]
        text = texts.get(name)
        written = _written_name(text) if text is not None else None
        if written is _LITERAL:
            continue
        if (
            isinstance(written, str)
            and written in parent.inputs
            and _same(parent.inputs[written], value)
        ):
            out[name] = written
            continue
        for pname, pvalue in parent.inputs.items():
            if pvalue is value and not isinstance(
                value, (bool, int, float, type(None))
            ):
                out[name] = pname
                break
    return out


# --------------------------------------------------------------------------- #
# Stamp -> LibraryRef
# --------------------------------------------------------------------------- #


def stamp_of(obj: Any) -> Optional[Dict[str, Any]]:
    """The plain record behind an instance's ``LibraryRef`` (or None)."""
    data = getattr(obj, "__dict__", None)
    return data.get(_STAMP_ATTR) if data else None


def _stamp(
    obj: Any, item: LibraryItem, inputs: Dict[str, Any], bindings: Dict[str, str]
) -> None:
    from .. import source_capture
    from ..gen.models import LibraryRef, StringParameter
    from .sources import source_string

    json_inputs = {}
    for name, value in inputs.items():
        try:
            json_inputs[name] = _to_json(value)
        except TypeError:
            continue
    configuration = item.match_configuration(inputs)
    source = source_string(item.import_root)
    record = {
        "item": item.id,
        "module": item.module,
        "cls": item.cls,
        "inputs": json_inputs,
        "configuration": configuration,
        "bindings": bindings or None,
        "source": source,
    }
    with source_capture.suspended():
        ref = LibraryRef(
            item=StringParameter(value=item.id),
            module=StringParameter(value=item.module),
            cls=StringParameter(value=item.cls),
            inputs=StringParameter(value=json.dumps(json_inputs)),
            configuration=(
                StringParameter(value=configuration) if configuration else None
            ),
            bindings=StringParameter(value=json.dumps(bindings)) if bindings else None,
            source=StringParameter(value=source) if source else None,
        )
    obj.__dict__[_STAMP_ATTR] = record
    obj.__dict__[_LIBRARY_REF_ATTR] = ref
