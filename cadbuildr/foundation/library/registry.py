"""The library registry: ``@part`` / ``@assembly`` / ``@operation`` and the manifest.

A library declares each configurable once (decorator + type hints). The
registry turns that declaration into a manifest item (``inputs`` with widgets,
``configurations``, ``anchors``...), which the viewer, the catalog sites, the
SDK and the agent all read.
"""

from __future__ import annotations

import dataclasses
import importlib
import inspect
import json
import pkgutil
import re
import sys
import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from .hints import (
    OneOfSpec,
    coerce_value,
    evaluate_annotation,
    humanize,
    widget_for,
)

__all__ = [
    "MANIFEST_FORMAT",
    "LibraryItem",
    "assembly",
    "discover",
    "find_item",
    "get_manifest",
    "item_for",
    "items",
    "library_id_for",
    "library_root_of",
    "operation",
    "part",
    "register",
]

MANIFEST_FORMAT = "cadbuildr.library-manifest/1"

_EMPTY = inspect.Parameter.empty

# (module, qualname) -> item. Last registration wins (re-imports, hot reload).
_REGISTRY: Dict[tuple, "LibraryItem"] = {}


# --------------------------------------------------------------------------- #
# Library roots and ids
# --------------------------------------------------------------------------- #

# Namespace packages whose sub-packages are each a library (cadbuildr.stdlib).
_NAMESPACES = ("cadbuildr",)


def library_root_of(module: str) -> str:
    """The import root of the library a module belongs to:
    ``cadbuildr.stdlib.bearings.x`` -> ``cadbuildr.stdlib``; ``my_parts.a`` -> ``my_parts``.
    """
    try:
        from .sources import library_entry_points

        matches = [
            r
            for r in library_entry_points()
            if module == r or module.startswith(r + ".")
        ]
        if matches:
            return max(matches, key=len)
    except Exception:  # pragma: no cover
        pass
    parts = (module or "").split(".")
    if len(parts) >= 2 and parts[0] in _NAMESPACES:
        return ".".join(parts[:2])
    return parts[0]


def library_id_for(import_root: str) -> str:
    """A library's id: ``LIBRARY_ID`` of its root package, else the last name
    of its import root (``cadbuildr.stdlib`` -> ``stdlib``)."""
    try:
        from .sources import library_id_for_root

        known = library_id_for_root(
            import_root
        )  # the cadbuildr.libraries entry point name
        if known:
            return known
    except Exception:  # pragma: no cover - sources is optional at import
        pass
    root = sys.modules.get(import_root)
    declared = getattr(root, "LIBRARY_ID", None) if root is not None else None
    if isinstance(declared, str) and declared:
        return declared
    return import_root.rsplit(".", 1)[-1]


# --------------------------------------------------------------------------- #
# Docstrings
# --------------------------------------------------------------------------- #

_ARGS_HEADER = re.compile(r"^\s*(Args|Arguments|Parameters|Inputs)\s*:\s*$")
_SECTION_HEADER = re.compile(r"^\s*[A-Z][A-Za-z ]*:\s*$")
_ARG_LINE = re.compile(r"^(\s*)(\*{0,2}\w+)\s*(\([^)]*\))?\s*:\s*(.*)$")


def parse_docstring(doc: Optional[str]) -> tuple[str, Dict[str, str]]:
    """(summary, {arg: description}) from a Google-style docstring."""
    if not doc:
        return "", {}
    text = inspect.cleandoc(doc)
    lines = text.splitlines()
    summary_lines: List[str] = []
    for line in lines:
        if not line.strip() or _ARGS_HEADER.match(line):
            break
        summary_lines.append(line.strip())
    args: Dict[str, str] = {}
    in_args = False
    current: Optional[str] = None
    indent = None
    for line in lines:
        if _ARGS_HEADER.match(line):
            in_args, current, indent = True, None, None
            continue
        if not in_args:
            continue
        if not line.strip():
            continue
        if _SECTION_HEADER.match(line) and (
            indent is None or len(line) - len(line.lstrip()) < indent
        ):
            in_args = False
            continue
        m = _ARG_LINE.match(line)
        line_indent = len(line) - len(line.lstrip())
        if m and (indent is None or line_indent <= indent):
            indent = line_indent
            current = m.group(2).lstrip("*")
            args[current] = m.group(4).strip()
        elif current is not None:
            args[current] = (args[current] + " " + line.strip()).strip()
    return " ".join(summary_lines), args


# --------------------------------------------------------------------------- #
# Items
# --------------------------------------------------------------------------- #


@dataclass
class LibraryItem:
    """One configurable: a decorated class (part / assembly) or function (operation)."""

    kind: str  # "part" | "assembly" | "operation" | "project"
    obj: Any  # the class or function
    module: str
    cls: str  # class / function name (qualname)
    name: str
    category: str = ""
    standard: Optional[str] = None
    description: Optional[str] = None
    thumbnail: Optional[str] = None
    presets: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    declared_anchors: Optional[List[str]] = None
    # Explicit per-input overrides: {name: {"widget": {...}, "label": ..., "description": ...}}
    overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # Extra metadata (catalog id, featured, example...).
    extra: Dict[str, Any] = field(default_factory=dict)
    item_id: Optional[str] = None
    # The function whose signature defines the inputs.
    signature_of: Any = None
    _inputs: Optional[List[Dict[str, Any]]] = None
    _hints: Optional[Dict[str, Any]] = None
    _anchors: Optional[List[str]] = None
    _interfaces: Optional[List[Dict[str, Any]]] = None

    # -- identity ---------------------------------------------------------- #
    @property
    def import_root(self) -> str:
        return library_root_of(self.module)

    @property
    def library_id(self) -> str:
        return library_id_for(self.import_root)

    @property
    def id(self) -> str:
        return self.item_id or f"{self.library_id}:{self.cls}"

    # -- inputs ------------------------------------------------------------ #
    def parameters(self) -> List[inspect.Parameter]:
        try:
            sig = inspect.signature(self.signature_of)
        except (TypeError, ValueError):
            return []
        params = list(sig.parameters.values())
        if self.kind in ("part", "assembly") and params and params[0].name == "self":
            params = params[1:]
        return [
            p
            for p in params
            if p.kind
            not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        ]

    def hints(self) -> Dict[str, Any]:
        if self._hints is None:
            owner = self.obj if isinstance(self.obj, type) else None
            self._hints = {
                p.name: evaluate_annotation(p.annotation, self.signature_of, owner)
                for p in self.parameters()
            }
        return self._hints

    def parameter_hint(self, name: str) -> Any:
        return self.hints().get(name, _EMPTY)

    def inputs(self) -> List[Dict[str, Any]]:
        if self._inputs is None:
            owner = self.obj if isinstance(self.obj, type) else None
            _, class_args = parse_docstring(getattr(self.obj, "__doc__", None))
            _, init_args = parse_docstring(getattr(self.signature_of, "__doc__", None))
            docs = {**class_args, **init_args}
            hints = self.hints()
            out = []
            for p in self.parameters():
                override = self.overrides.get(p.name, {})
                if "widget" in override:
                    widget = dict(override["widget"])
                else:
                    widget = widget_for(hints.get(p.name, _EMPTY), p.default, owner)
                entry: Dict[str, Any] = {
                    "name": p.name,
                    "label": override.get("label") or humanize(p.name),
                    "required": p.default is _EMPTY,
                    "hasDefault": p.default is not _EMPTY,
                    "widget": widget,
                }
                description = override.get("description") or docs.get(p.name)
                if description:
                    entry["description"] = description
                out.append(entry)
            self._inputs = out
        return self._inputs

    def input(self, name: str) -> Optional[Dict[str, Any]]:
        for entry in self.inputs():
            if entry["name"] == name:
                return entry
        return None

    def defaults(self) -> Dict[str, Any]:
        return {p.name: p.default for p in self.parameters() if p.default is not _EMPTY}

    def coerce_inputs(self, values: Dict[str, Any]) -> Dict[str, Any]:
        """Widget values (JSON) -> constructor arguments."""
        hints = self.hints()
        out = {}
        for name, value in values.items():
            entry = self.input(name)
            if entry is None:
                out[name] = value
                continue
            out[name] = coerce_value(entry["widget"], hints.get(name, _EMPTY), value)
        return out

    # -- configurations ---------------------------------------------------- #
    def configurations(self) -> List[Dict[str, Any]]:
        """Declared presets first, then the rows of each ``OneOf[TABLE]`` input."""
        out: List[Dict[str, Any]] = []
        seen = set()
        for name, values in self.presets.items():
            out.append({"name": name, "values": _jsonable_dict(values)})
            seen.add(name)
        for pname, hint in self.hints().items():
            spec = _one_of(hint)
            if spec is None or spec.table is None:
                continue
            for value, label in zip(spec.values, spec.labels()):
                if label in seen:
                    continue
                seen.add(label)
                out.append({"name": label, "values": {pname: _to_json(value)}})
        return out

    def match_configuration(self, inputs: Dict[str, Any]) -> Optional[str]:
        """The configuration whose values equal ``inputs`` (other inputs at
        their defaults), presets first."""
        defaults = self.defaults()
        jin = _jsonable_dict(inputs)
        jdef = _jsonable_dict(defaults)
        for config in self.configurations():
            values = config["values"]
            if any(jin.get(k) != v for k, v in values.items()):
                continue
            rest_ok = all(
                k in values or (k in jdef and jdef[k] == v) for k, v in jin.items()
            )
            if rest_ok:
                return config["name"]
        return None

    def sample_inputs(self) -> Optional[Dict[str, Any]]:
        """Constructor arguments for a representative instance (defaults,
        widget defaults, the declared ``example``), or None if one is missing."""
        kwargs: Dict[str, Any] = {}
        example = dict(self.extra.get("example") or {})
        for p in self.parameters():
            if p.name in example:
                continue
            if p.default is not _EMPTY:
                continue
            entry = self.input(p.name)
            widget = entry["widget"] if entry else {}
            if "default" in widget and widget.get("kind") in (
                "enum",
                "number",
                "bool",
                "text",
            ):
                kwargs[p.name] = widget["default"]
            else:
                return None
        kwargs.update(example)
        return self.coerce_inputs(kwargs)

    # -- anchors ------------------------------------------------------------ #
    def _sample(self) -> None:
        """Build the default instance once: its anchor names and interfaces."""
        self._anchors, self._interfaces = [], []
        kwargs = self.sample_inputs()
        if self.kind not in ("part", "assembly") or kwargs is None:
            return
        try:
            from .. import source_capture
            from .stamp import suspended as stamp_suspended

            with source_capture.suspended(), stamp_suspended(), warnings.catch_warnings():
                warnings.simplefilter("ignore")
                instance = self.obj(**kwargs)
            self._anchors = [a.name.value for a in getattr(instance, "anchors", [])]
            self._interfaces = describe_interfaces(instance)
        except Exception:
            self._anchors, self._interfaces = [], []

    def anchors(self) -> List[str]:
        if self.declared_anchors is not None:
            return list(self.declared_anchors)
        if self._anchors is None:
            self._sample()
        return list(self._anchors)

    def interfaces(self) -> List[Dict[str, Any]]:
        """The interfaces (name, type, params, role, group, required) the
        default instance exposes."""
        if self._interfaces is None:
            self._sample()
        return [dict(i) for i in self._interfaces]

    # -- manifest ----------------------------------------------------------- #
    def to_manifest(self, with_anchors: bool = True) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "id": self.id,
            "kind": self.kind,
            "module": self.module,
            "cls": self.cls,
            "name": self.name,
            "category": self.category,
            "standard": self.standard,
            "description": self.description,
            "inputs": self.inputs(),
            "configurations": self.configurations(),
            "thumbnail": self.thumbnail,
        }
        if with_anchors:
            out["anchors"] = self.anchors()
            out["interfaces"] = self.interfaces()
        if self.extra.get("featured"):
            out["featured"] = True
        return out

    def load(self) -> Any:
        module = importlib.import_module(self.module)
        obj = module
        for part in self.cls.split("."):
            obj = getattr(obj, part)
        return obj


def describe_interfaces(instance: Any) -> List[Dict[str, Any]]:
    """``[{name, type, params, role, group, required}]`` of a built component."""
    out = []
    for node in getattr(instance, "interfaces", None) or []:
        try:
            params = json.loads(node.params.value or "{}")
        except ValueError:
            params = {}
        out.append(
            {
                "name": node.anchor.name.value,
                "type": node.type.value,
                "params": params,
                "role": node.role.value if node.role is not None else None,
                "group": node.group.value if node.group is not None else None,
                "required": (
                    bool(node.required.value) if node.required is not None else False
                ),
            }
        )
    return out


def _one_of(hint: Any) -> Optional[OneOfSpec]:
    import typing

    if typing.get_origin(hint) is typing.Annotated:
        for m in typing.get_args(hint)[1:]:
            if isinstance(m, OneOfSpec):
                return m
    if isinstance(hint, OneOfSpec):
        return hint
    return None


def _to_json(value: Any) -> Any:
    import enum

    if isinstance(value, enum.Enum):
        return value.name
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {k: _to_json(v) for k, v in dataclasses.asdict(value).items()}
    if isinstance(value, (list, tuple)):
        return [_to_json(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _to_json(v) for k, v in value.items()}
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    try:
        import numpy as np

        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, np.ndarray):
            return value.tolist()
    except Exception:  # pragma: no cover
        pass
    raise TypeError(f"not JSON-serializable: {type(value).__name__}")


def _jsonable_dict(values: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for k, v in values.items():
        try:
            out[k] = _to_json(v)
        except TypeError:
            continue
    return out


# --------------------------------------------------------------------------- #
# Decorators
# --------------------------------------------------------------------------- #


def register(item: LibraryItem) -> LibraryItem:
    _REGISTRY[(item.module, item.cls)] = item
    return item


def _original_init(cls: type) -> Any:
    init = cls.__dict__.get("__init__")
    if init is None:
        init = cls.__init__
    # Foundation's auto-init wrapper keeps the user's __init__ here.
    return getattr(init, "__foundation_original_init__", init)


def _make_item(kind: str, obj: Any, kwargs: Dict[str, Any]) -> LibraryItem:
    is_class = isinstance(obj, type)
    summary, _ = parse_docstring(getattr(obj, "__doc__", None))
    configurations = kwargs.pop("configurations", None) or {}
    item = LibraryItem(
        kind=kind,
        obj=obj,
        module=obj.__module__,
        cls=obj.__qualname__,
        name=kwargs.pop("name", None) or humanize(obj.__name__),
        category=kwargs.pop("category", None) or "",
        standard=kwargs.pop("standard", None),
        description=kwargs.pop("description", None) or (summary or None),
        thumbnail=kwargs.pop("thumbnail", None),
        presets={k: dict(v) for k, v in dict(configurations).items()},
        declared_anchors=kwargs.pop("anchors", None),
        overrides=dict(kwargs.pop("inputs", None) or {}),
        item_id=kwargs.pop("id", None),
        signature_of=_original_init(obj) if is_class else obj,
    )
    item.extra.update(kwargs)
    return item


def _decorator(kind: str, target: Any, kwargs: Dict[str, Any]) -> Any:
    def wrap(obj: Any) -> Any:
        item = _make_item(kind, obj, dict(kwargs))
        register(item)
        if kind in ("part", "assembly"):
            from .stamp import install

            install(obj, item)
        obj.__library_item__ = item
        return obj

    if target is not None:
        return wrap(target)
    return wrap


def part(_cls: Any = None, **kwargs: Any) -> Any:
    """Declare a ``Part`` subclass as a library part.

    Keyword arguments: ``category`` ("Bearings/Ball"), ``name``, ``standard``,
    ``description`` (default: the class docstring's summary),
    ``configurations`` ({name: {input: value}} presets), ``anchors`` (names,
    default: read from a default instance), ``thumbnail``, ``id`` (default
    ``<library>:<ClassName>``), ``inputs`` (per-input overrides
    ``{name: {"widget"|"label"|"description": ...}}``); anything else is kept
    as extra metadata (``featured``, ``example``...).
    """
    return _decorator("part", _cls, kwargs)


def assembly(_cls: Any = None, **kwargs: Any) -> Any:
    """Declare an ``Assembly`` subclass as a library assembly (same keywords as :func:`part`)."""
    return _decorator("assembly", _cls, kwargs)


def operation(_func: Any = None, **kwargs: Any) -> Any:
    """Declare a function acting on existing components (a joint, a cut) as a
    library operation. Operations are listed in the manifest but are not
    evaluable alone.

    An operation may return a :class:`cadbuildr.foundation.checks.Report`
    next to its geometry (fits, screening results), e.g. ``return part,
    report``. ``report.attach(component)`` puts the report's issues in that
    component's ``check()`` and in the DAG ``checks`` the viewer shows;
    ``@operation(report=True)`` records in the manifest that it does.
    """
    return _decorator("operation", _func, kwargs)


# --------------------------------------------------------------------------- #
# Lookup and discovery
# --------------------------------------------------------------------------- #


def items(import_root: Optional[str] = None) -> List[LibraryItem]:
    out = list(_REGISTRY.values())
    if import_root:
        out = [
            i
            for i in out
            if i.module == import_root or i.module.startswith(import_root + ".")
        ]
    return out


def item_for(obj: Any) -> Optional[LibraryItem]:
    item = obj.__dict__.get("__library_item__") if hasattr(obj, "__dict__") else None
    if item is None:
        item = getattr(obj, "__library_item__", None)
        if item is not None and item.obj is not obj:
            return None
    return item


def find_item(item_id: str) -> Optional[LibraryItem]:
    for item in _REGISTRY.values():
        if item.id == item_id:
            return item
    return None


def forget(import_root: str) -> None:
    """Drop the registered items of a library (before a hot reload)."""
    for key in [
        k
        for k in _REGISTRY
        if k[0] == import_root or k[0].startswith(import_root + ".")
    ]:
        del _REGISTRY[key]


_SKIP_MODULE_NAMES = {"__main__", "conftest", "setup"}


def discover(import_root: str, errors: Optional[List[str]] = None) -> List[LibraryItem]:
    """Import every module under ``import_root`` so its decorators run, and
    return the library's items. Works from a checkout, a wheel and a
    zipimport (``pkgutil.walk_packages``)."""
    root = importlib.import_module(import_root)
    if hasattr(root, "__path__"):
        for info in pkgutil.walk_packages(root.__path__, prefix=import_root + "."):
            leaf = info.name.rsplit(".", 1)[-1]
            if (
                leaf in _SKIP_MODULE_NAMES
                or leaf.startswith("test")
                or ".tests" in info.name
            ):
                continue
            if info.name in sys.modules:
                continue
            try:
                importlib.import_module(info.name)
            except Exception as exc:  # a broken module must not hide the rest
                if errors is not None:
                    errors.append(f"{info.name}: {type(exc).__name__}: {exc}")
    return sorted(items(import_root), key=lambda i: (i.category, i.name, i.cls))


# --------------------------------------------------------------------------- #
# Manifest
# --------------------------------------------------------------------------- #


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "items"


def default_toolbar(
    library_name: str, lib_items: Iterable[LibraryItem]
) -> Dict[str, Any]:
    """One tab per library, one section per top-level category."""
    sections: Dict[str, Dict[str, Any]] = {}
    for item in lib_items:
        top = (item.category or "Other").split("/", 1)[0].strip() or "Other"
        section = sections.setdefault(
            _slug(top), {"id": _slug(top), "label": top, "items": []}
        )
        section["items"].append(item.id)
    return {"tab": library_name, "sections": list(sections.values())}


def _toolbar(
    root: Any, tab: str, lib_items: List[LibraryItem], library_id: str
) -> Dict[str, Any]:
    declared = getattr(root, "TOOLBAR", None)
    if not isinstance(declared, dict):
        return default_toolbar(tab, lib_items)
    toolbar = {"tab": declared.get("tab", tab), "sections": []}
    for section in declared.get("sections", []):
        ids = [i if ":" in i else f"{library_id}:{i}" for i in section.get("items", [])]
        toolbar["sections"].append(
            {
                "id": section.get("id") or _slug(section.get("label", "items")),
                "label": section.get("label") or section.get("id", "Items"),
                "items": ids,
            }
        )
    return toolbar


def _distribution_version(import_root: str) -> Optional[str]:
    try:
        from importlib import metadata

        top = import_root.split(".")[0]
        names = metadata.packages_distributions().get(top, [])
        root_mod = sys.modules.get(import_root)
        candidates = list(names)
        guess = import_root.replace(".", "-").replace("_", "-")
        if guess in [n.lower() for n in candidates] or not candidates:
            candidates.insert(0, guess)
        for name in candidates:
            try:
                dist = metadata.distribution(name)
            except metadata.PackageNotFoundError:
                continue
            files = dist.files or []
            rel = import_root.replace(".", "/")
            if (
                name == guess
                or any(str(f).startswith(rel) for f in files)
                or _editable_covers(dist, root_mod)
            ):
                return dist.version
    except Exception:
        return None
    return None


def _editable_covers(dist: Any, root_mod: Any) -> bool:
    try:
        text = dist.read_text("direct_url.json")
        if not text or root_mod is None:
            return False
        url = json.loads(text).get("url", "")
        path = url.replace("file://", "")
        mod_file = getattr(root_mod, "__file__", "") or ""
        return bool(path) and mod_file.startswith(path.rstrip("/") + "/")
    except Exception:
        return False


def library_info(import_root: str) -> Dict[str, Any]:
    root = sys.modules.get(import_root) or importlib.import_module(import_root)
    library_id = library_id_for(import_root)
    name = getattr(root, "LIBRARY_NAME", None) or humanize(library_id.replace("-", "_"))
    from .sources import source_of

    source = source_of(import_root)
    version = getattr(root, "__version__", None) or _distribution_version(import_root)
    return {
        "id": library_id,
        "name": name,
        "import_root": import_root,
        "version": version,
        "source": source,
    }


def get_manifest(
    import_root: str,
    with_anchors: bool = True,
    errors: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """The ``cadbuildr.library-manifest/1`` document of one library."""
    errs: List[str] = [] if errors is None else errors
    lib_items = discover(import_root, errs)
    info = library_info(import_root)
    root = sys.modules[import_root]
    tab = getattr(root, "LIBRARY_TAB", None) or humanize(info["id"].replace("-", "_"))
    manifest: Dict[str, Any] = {
        "format": MANIFEST_FORMAT,
        "library": info,
        "toolbar": _toolbar(
            root, tab, [i for i in lib_items if i.kind != "project"], info["id"]
        ),
        "items": [i.to_manifest(with_anchors=with_anchors) for i in lib_items],
    }
    if errs:
        manifest["errors"] = errs
    return manifest


def call_configurable(item: LibraryItem, values: Dict[str, Any]) -> Any:
    """Build ``item`` from widget values (``Cls(**inputs)``)."""
    if item.kind == "operation":
        raise TypeError("operations are not evaluable alone")
    target = item.load() if item.obj is None else item.obj
    kwargs = item.coerce_inputs(values)
    return target(**kwargs)
