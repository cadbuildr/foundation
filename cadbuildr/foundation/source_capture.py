"""Record where each DAG node was built in user code (opt-in).

The browser viewer lets a user edit a value after a build; to turn that edit
into a code change, every node needs to point back at the line of user Python
that produced it. With capture on, each foundation model records, at
construction time:

- ``src``: the call expression that built it, in the first stack frame outside
  the ``cadbuildr`` packages, pydantic and the standard library;
- ``fieldSrc``: for each field whose value was passed at that call, the
  argument's own location and source text (``"10"``, ``"width"``,
  ``"width * 2"``).

``show`` / ``show_dag(..., with_source=True)`` then emit them on each node next
to ``type`` / ``params`` / ``deps``::

    {"type": 12, "params": {}, "deps": {"end": "a1f3", ...},
     "src": {"file": "parts/bracket.py", "line": 42, "col": 4, "endCol": 21,
             "text": "Extrusion(sk, 10)"},
     "fieldSrc": {"end": {"file": "parts/bracket.py", "line": 42, "col": 18,
                          "endCol": 20, "text": "10"}}}

``line`` is 1-based; ``col`` / ``endCol`` are 0-based character offsets on that
line (``endCol`` exclusive, present only for single-line spans). ``file`` is
relative to the source root (``set_root``, ``CADBUILDR_SOURCE_ROOT``, else the
working directory) when the file is under it.

Nodes are deduplicated by content hash, so one ``FloatParameter(10)`` used by
two features is one node: per-use locations live on the *owner* node's
``fieldSrc``. Source metadata is attached after hashing, so node ids are
byte-identical with and without it.

Capture must be on while the model code runs (it happens at construction), so
a runtime calls :func:`enable` (or uses :func:`capturing`) before executing
user code, or sets ``CADBUILDR_WITH_SOURCE=1`` before ``cadbuildr.foundation``
is imported. When it was never enabled nothing is installed and construction is
unchanged; after :func:`disable` the only cost left is a flag check. Capture
never raises: on any failure the node simply has no ``src``.

Columns come from ``code.co_positions()`` (Python 3.11+); on 3.10 ``src`` has
only ``file`` and ``line`` and there is no ``fieldSrc``. Source text is read
through :mod:`linecache`, so code run with ``exec`` must be compiled with a
real filename (and registered in ``linecache`` if no file exists on disk).
"""

from __future__ import annotations

import ast
import linecache
import numbers
import os
import sys
import sysconfig
from contextlib import contextmanager
from enum import Enum
from typing import Any, Dict, Iterator, List, Optional, Tuple

from pydantic import BaseModel

from .gen.dag.conversion import SOURCE_ATTR, get_source

__all__ = [
    "ENV_VAR",
    "ROOT_ENV_VAR",
    "SOURCE_ATTR",
    "add_internal_path",
    "capturing",
    "disable",
    "enable",
    "get_source",
    "is_enabled",
    "set_root",
    "suspended",
]

ENV_VAR = "CADBUILDR_WITH_SOURCE"
ROOT_ENV_VAR = "CADBUILDR_SOURCE_ROOT"

_ENABLED = False
_SUSPENDED = 0
_INSTALLED = False
_ROOT: Optional[str] = None
_EXTRA_INTERNAL: List[str] = []

_MAX_CALL_TEXT = 200
# Longer list arguments/fields are not matched by value (cost, ambiguity).
_MAX_LIST_MATCH = 16
_MISSING = object()
_CO_VARARGS = 0x04
_CO_VARKEYWORDS = 0x08

# filename -> True when the frame belongs to library code (skipped).
_INTERNAL_CACHE: Dict[str, bool] = {}
# filename -> path as emitted in ``file``.
_DISPLAY_CACHE: Dict[str, str] = {}
# code object -> list of co_positions() entries.
_POSITIONS_CACHE: Dict[Any, list] = {}
# (code object, f_lasti) -> _CallSite
_SITE_CACHE: Dict[Tuple[Any, int], "_CallSite"] = {}


# --------------------------------------------------------------------------- #
# Public switch
# --------------------------------------------------------------------------- #


def is_enabled() -> bool:
    """True while construction-time capture is on."""
    return _ENABLED


def enable(root: Optional[str] = None) -> None:
    """Turn capture on for models built from now on.

    Args:
        root: Directory ``file`` paths are made relative to (default: the
            ``CADBUILDR_SOURCE_ROOT`` env var, else the working directory at
            capture time).
    """
    global _ENABLED
    if root is not None:
        set_root(root)
    _install()
    _ENABLED = True


def disable() -> None:
    """Turn capture off. Already-recorded locations are kept."""
    global _ENABLED
    _ENABLED = False


@contextmanager
def capturing(root: Optional[str] = None) -> Iterator[None]:
    """Capture source locations inside the ``with`` block."""
    previous = _ENABLED
    enable(root)
    try:
        yield
    finally:
        if not previous:
            disable()


@contextmanager
def suspended() -> Iterator[None]:
    """Skip capture inside the block (e.g. objects built while serializing)."""
    global _SUSPENDED
    _SUSPENDED += 1
    try:
        yield
    finally:
        _SUSPENDED -= 1


def set_root(root: Optional[str]) -> None:
    """Set the directory ``file`` paths are made relative to (None: cwd)."""
    global _ROOT
    _ROOT = os.path.abspath(root) if root else None
    _DISPLAY_CACHE.clear()
    _SITE_CACHE.clear()


def add_internal_path(path: str) -> None:
    """Treat frames from files under ``path`` as library code (skipped)."""
    _EXTRA_INTERNAL.append(os.path.abspath(path))
    _INTERNAL_CACHE.clear()
    _SITE_CACHE.clear()


# --------------------------------------------------------------------------- #
# Installation: wrap every generated model's __init__ (only once enabled).
# --------------------------------------------------------------------------- #


def _install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from .gen import models

    for value in list(vars(models).values()):
        if (
            isinstance(value, type)
            and issubclass(value, BaseModel)
            and value.__module__.startswith(models.__name__)
        ):
            _wrap_init(value)
    _INSTALLED = True


def _wrap_init(cls: type) -> None:
    own = cls.__dict__.get("__init__")
    if getattr(own, "__cadbuildr_source_capture__", False):
        return

    if own is None:

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super(cls, self).__init__(*args, **kwargs)
            if _ENABLED and not _SUSPENDED and SOURCE_ATTR not in self.__dict__:
                _capture(self, args, kwargs)

    else:

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            own(self, *args, **kwargs)
            if _ENABLED and not _SUSPENDED and SOURCE_ATTR not in self.__dict__:
                _capture(self, args, kwargs)

        __init__.__wrapped__ = own  # type: ignore[attr-defined]

    __init__.__qualname__ = f"{cls.__qualname__}.__init__"
    __init__.__doc__ = getattr(own, "__doc__", None)
    __init__.__cadbuildr_source_capture__ = True  # type: ignore[attr-defined]
    cls.__init__ = __init__  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# Frame filtering and paths
# --------------------------------------------------------------------------- #


def _library_dirs() -> List[str]:
    dirs: List[str] = []
    try:
        import cadbuildr

        dirs.extend(os.path.abspath(p) for p in list(cadbuildr.__path__))
    except Exception:
        pass
    dirs.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for mod_name in ("pydantic", "pydantic_core", "typing_extensions"):
        mod = sys.modules.get(mod_name)
        mod_file = getattr(mod, "__file__", None)
        if mod_file:
            if os.path.basename(mod_file) == "__init__.py":
                dirs.append(os.path.dirname(os.path.abspath(mod_file)))
            else:
                dirs.append(os.path.abspath(mod_file))
    dirs.extend(_EXTRA_INTERNAL)
    return dirs


def _site_dirs() -> List[str]:
    paths = sysconfig.get_paths()
    return [os.path.abspath(paths[k]) for k in ("purelib", "platlib") if k in paths]


def _stdlib_dirs() -> List[str]:
    paths = sysconfig.get_paths()
    return [os.path.abspath(paths[k]) for k in ("stdlib", "platstdlib") if k in paths]


def _under(path: str, base: str) -> bool:
    return path == base or path.startswith(base.rstrip(os.sep) + os.sep)


def _is_internal(filename: str) -> bool:
    cached = _INTERNAL_CACHE.get(filename)
    if cached is not None:
        return cached
    if filename.startswith("<"):
        # "<frozen importlib._bootstrap>" is the interpreter; "<string>",
        # "<exec>", "<stdin>" are user code run without a file.
        result = filename.startswith("<frozen")
    else:
        path = os.path.abspath(filename)
        if any(_under(path, d) for d in _library_dirs()):
            result = True
        elif any(_under(path, d) for d in _site_dirs()):
            result = False
        else:
            result = any(_under(path, d) for d in _stdlib_dirs())
    _INTERNAL_CACHE[filename] = result
    return result


def _frame_is_internal(frame: Any, depth: int = 0) -> bool:
    filename = frame.f_code.co_filename
    if _is_internal(filename):
        return True
    if filename.startswith("<") and depth < 4:
        # Code a library evaluates (``eval("FloatParameter(value=0.0)")`` in
        # the generated runtime) is part of that library.
        back = frame.f_back
        return back is not None and _frame_is_internal(back, depth + 1)
    return False


def _display_path(filename: str) -> str:
    cached = _DISPLAY_CACHE.get(filename)
    if cached is not None:
        return cached
    result = filename
    if not filename.startswith("<"):
        root = _ROOT or os.environ.get(ROOT_ENV_VAR) or os.getcwd()
        path = os.path.abspath(filename)
        root = os.path.abspath(root)
        if _under(path, root):
            result = os.path.relpath(path, root)
        else:
            result = path
        result = result.replace(os.sep, "/")
    _DISPLAY_CACHE[filename] = result
    return result


# --------------------------------------------------------------------------- #
# Call-site parsing (cached per code object + instruction)
# --------------------------------------------------------------------------- #


class _CallSite:
    __slots__ = ("src", "positional", "keywords", "is_method_call", "complete")

    def __init__(self, src: Dict[str, Any]) -> None:
        self.src = src
        # One ref per positional argument (None for a ``*args`` splat).
        self.positional: List[Optional[Dict[str, Any]]] = []
        # Keyword name -> ref (``**kwargs`` splats are skipped).
        self.keywords: Dict[str, Dict[str, Any]] = {}
        # ``obj.method(...)``: the callee's first parameter is bound.
        self.is_method_call = False
        # False when positions are unknowable (a ``*args`` splat).
        self.complete = True


def _char_col(line: str, byte_col: int) -> int:
    if line.isascii():
        return byte_col
    return len(line.encode("utf-8")[:byte_col].decode("utf-8", errors="ignore"))


def _code_positions(code: Any) -> Optional[list]:
    positions = _POSITIONS_CACHE.get(code)
    if positions is None:
        co_positions = getattr(code, "co_positions", None)
        if co_positions is None:
            return None
        positions = list(co_positions())
        _POSITIONS_CACHE[code] = positions
    return positions


def _slice(lines: List[str], l1: int, c1: int, l2: int, c2: int) -> str:
    """Text between two (1-based line, byte col) positions."""
    if l1 == l2:
        return lines[l1 - 1].encode("utf-8")[c1:c2].decode("utf-8", errors="replace")
    first = lines[l1 - 1].encode("utf-8")[c1:].decode("utf-8", errors="replace")
    last = lines[l2 - 1].encode("utf-8")[:c2].decode("utf-8", errors="replace")
    return first + "".join(lines[l1 : l2 - 1]) + last


def _ref(
    file: str,
    lines: List[str],
    l1: int,
    c1: int,
    l2: int,
    c2: int,
    text: Optional[str],
) -> Dict[str, Any]:
    ref: Dict[str, Any] = {
        "file": file,
        "line": l1,
        "col": _char_col(lines[l1 - 1], c1),
    }
    if l1 == l2:
        ref["endCol"] = _char_col(lines[l2 - 1], c2)
    if text is not None:
        ref["text"] = text
    return ref


def _build_site(frame: Any) -> _CallSite:
    code = frame.f_code
    filename = code.co_filename
    file = _display_path(filename)
    positions = _code_positions(code)
    index = frame.f_lasti // 2
    if positions is None or not 0 <= index < len(positions):
        return _CallSite({"file": file, "line": frame.f_lineno})
    l1, l2, c1, c2 = positions[index]
    if l1 is None:
        return _CallSite({"file": file, "line": frame.f_lineno})
    lines = linecache.getlines(filename, frame.f_globals)
    if c1 is None or c2 is None or l2 is None or len(lines) < l2:
        return _CallSite({"file": file, "line": l1})

    segment = _slice(lines, l1, c1, l2, c2)
    call_text = segment if l1 == l2 and len(segment) <= _MAX_CALL_TEXT else None
    site = _CallSite(_ref(file, lines, l1, c1, l2, c2, call_text))
    try:
        node = ast.parse(segment, mode="eval").body
    except SyntaxError:
        return site
    if not isinstance(node, ast.Call):
        return site

    def arg_ref(arg: ast.AST) -> Dict[str, Any]:
        a1 = l1 + arg.lineno - 1
        a2 = l1 + arg.end_lineno - 1  # type: ignore[attr-defined]
        b1 = arg.col_offset + (c1 if arg.lineno == 1 else 0)
        b2 = arg.end_col_offset + (c1 if arg.end_lineno == 1 else 0)  # type: ignore[attr-defined]
        return _ref(file, lines, a1, b1, a2, b2, ast.get_source_segment(segment, arg))

    site.is_method_call = isinstance(node.func, ast.Attribute)
    for arg in node.args:
        if isinstance(arg, ast.Starred):
            site.positional.append(None)
            site.complete = False
        else:
            site.positional.append(arg_ref(arg))
    for kw in node.keywords:
        if kw.arg is not None:
            site.keywords[kw.arg] = arg_ref(kw.value)
    return site


# --------------------------------------------------------------------------- #
# Capture
# --------------------------------------------------------------------------- #


def _capture(obj: Any, args: Tuple[Any, ...], kwargs: Dict[str, Any]) -> None:
    try:
        callee = sys._getframe(1)  # the wrapper's frame
        frame = callee.f_back
        cache = _INTERNAL_CACHE
        while frame is not None:
            # Inlined fast path of _frame_is_internal (hot: every model built).
            internal = cache.get(frame.f_code.co_filename)
            if internal is False or (
                internal is None and not _frame_is_internal(frame)
            ):
                if frame.f_code.co_filename[:1] != "<" or not _frame_is_internal(frame):
                    break
            callee = frame
            frame = frame.f_back
        if frame is None:
            return
        key = (frame.f_code, frame.f_lasti)
        site = _SITE_CACHE.get(key)
        if site is None:
            site = _build_site(frame)
            _SITE_CACHE[key] = site
        meta: Dict[str, Any] = {"src": site.src}
        if site.positional or site.keywords:
            field_src = _map_fields(obj, site, callee, args, kwargs)
            if field_src:
                meta["fieldSrc"] = field_src
        obj.__dict__[SOURCE_ATTR] = meta
    except Exception:
        pass


def _call_items(
    obj: Any,
    site: _CallSite,
    callee: Any,
    args: Tuple[Any, ...],
    kwargs: Dict[str, Any],
) -> List[Tuple[Optional[str], Any, Dict[str, Any]]]:
    """(parameter name, value, ref) for each argument written at the call."""
    items: List[Tuple[Optional[str], Any, Dict[str, Any]]] = []
    callee_code = callee.f_code
    names = callee_code.co_varnames
    direct = bool(names) and names[0] == "self" and callee.f_locals.get("self") is obj

    if direct:
        # The user called this model's constructor: positionals land in the
        # generated ``__positional_fields__`` order; values are the wrapper's.
        fields = getattr(type(obj), "__positional_fields__", ())
        known = site.complete and len(args) == len(site.positional)
        for i, ref in enumerate(site.positional):
            if ref is None:
                continue
            name = fields[i] if site.complete and i < len(fields) else None
            value = args[i] if known else _MISSING
            items.append((name, value, ref))
        for name, ref in site.keywords.items():
            items.append((name, kwargs.get(name, _MISSING), ref))
        return items

    # The user called a function (``part.extrude(sk, 10)``): positionals map
    # to its parameters, values come from its frame.
    if type(obj).__name__.endswith("Parameter"):
        # A parameter built inside a library call is deduplicated by value and
        # shared; its per-use location belongs on the owner's ``fieldSrc``.
        return items
    local_vars = callee.f_locals
    argcount = callee_code.co_argcount
    params = list(names[:argcount])
    flags = callee_code.co_flags
    star_name = (
        names[argcount + callee_code.co_kwonlyargcount] if flags & _CO_VARARGS else None
    )
    kw_index = argcount + callee_code.co_kwonlyargcount + (1 if star_name else 0)
    kw_name = names[kw_index] if flags & _CO_VARKEYWORDS else None
    bound = site.is_method_call or callee_code.co_name in ("__init__", "__new__")
    if bound and params and params[0] in ("self", "cls"):
        params = params[1:]
    star_values = local_vars.get(star_name, ()) if star_name else ()
    if site.complete:
        for i, ref in enumerate(site.positional):
            if i < len(params):
                items.append((params[i], local_vars.get(params[i], _MISSING), ref))
            else:
                j = i - len(params)
                value = star_values[j] if j < len(star_values) else _MISSING
                items.append((None, value, ref))
    extra_kwargs = local_vars.get(kw_name, {}) if kw_name else {}
    for name, ref in site.keywords.items():
        if name in local_vars and name in names:
            value = local_vars.get(name, _MISSING)
        else:
            value = (
                extra_kwargs.get(name, _MISSING)
                if isinstance(extra_kwargs, dict)
                else _MISSING
            )
        items.append((name, value, ref))
    return items


def _primitive(value: Any) -> Any:
    """Unwrap ``*Parameter`` models to their ``value``."""
    if isinstance(value, BaseModel):
        data = value.__dict__
        if "value" in data and type(value).__name__.endswith("Parameter"):
            return data["value"]
    return value


def _matches(field_value: Any, value: Any) -> bool:
    if field_value is value:
        return True
    if isinstance(value, BaseModel):
        return isinstance(field_value, (list, tuple)) and any(
            v is value for v in field_value
        )
    if isinstance(value, (list, tuple)):
        return (
            isinstance(field_value, (list, tuple))
            and len(field_value) == len(value)
            and all(_matches(a, b) for a, b in zip(field_value, value))
        )
    inner = _primitive(field_value)
    if isinstance(value, bool) or isinstance(inner, bool):
        return isinstance(value, bool) and isinstance(inner, bool) and inner == value
    if isinstance(value, str):
        return isinstance(inner, str) and inner == value
    if isinstance(value, numbers.Real):
        return isinstance(inner, numbers.Real) and inner == value
    return False


def _map_fields(
    obj: Any,
    site: _CallSite,
    callee: Any,
    args: Tuple[Any, ...],
    kwargs: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    items = _call_items(obj, site, callee, args, kwargs)
    if not items:
        return {}
    data = obj.__dict__
    fields = type(obj).model_fields
    out: Dict[str, Dict[str, Any]] = {}
    pending = []
    # 1. By name (keyword, or the callee's parameter name).
    for name, value, ref in items:
        if (
            name is not None
            and name in fields
            and name not in out
            and (value is _MISSING or _matches(data.get(name), value))
        ):
            out[name] = ref
        else:
            pending.append((value, ref))
    # 2. By value: the one remaining field holding exactly that value/object.
    index: Optional[Dict[Any, List[str]]] = None
    for value, ref in pending:
        key = _value_key(value)
        if key is None:
            continue
        if index is None:
            index = _field_index(data, fields)
        candidates = [f for f in index.get(key, ()) if f not in out]
        if len(candidates) == 1:
            out[candidates[0]] = ref
    return out


def _value_key(value: Any) -> Any:
    """Hashable identity of an argument value for matching (None: unmatchable)."""
    if value is _MISSING or value is None:
        return None
    if isinstance(value, BaseModel):
        return ("m", id(value))
    if isinstance(value, Enum):
        value = value.value
    if isinstance(value, bool):
        return ("b", value)
    if isinstance(value, str):
        return ("s", str(value))
    if isinstance(value, numbers.Real):
        return ("n", float(value))
    if isinstance(value, (list, tuple)) and len(value) <= _MAX_LIST_MATCH:
        keys = tuple(_value_key(v) for v in value)
        return None if None in keys else ("l", keys)
    return None


def _field_index(data: Dict[str, Any], fields: Any) -> Dict[Any, List[str]]:
    """Value key -> fields of the model holding that value."""
    index: Dict[Any, List[str]] = {}

    def add(key: Any, field: str) -> None:
        if key is not None:
            names = index.setdefault(key, [])
            if field not in names:
                names.append(field)

    for field in fields:
        fv = data.get(field)
        if fv is None:
            continue
        add(_value_key(fv), field)
        if isinstance(fv, BaseModel):
            inner = _primitive(fv)
            if inner is not fv:
                add(_value_key(inner), field)
        elif isinstance(fv, (list, tuple)) and len(fv) <= _MAX_LIST_MATCH:
            for item in fv:
                if isinstance(item, BaseModel):
                    add(("m", id(item)), field)
            add(_value_key([_primitive(v) for v in fv]), field)
    return index


def _env_enabled() -> bool:
    return os.environ.get(ENV_VAR, "").strip().lower() in ("1", "true", "yes", "on")


if _env_enabled():
    enable()
