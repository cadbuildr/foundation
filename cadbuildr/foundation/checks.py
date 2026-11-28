"""Design checks: one issue shape, one hook, collected over the whole tree.

Every check in foundation returns issues shaped like ``Assembly.check()``::

    {severity, code, interfaces, components, delta, message, fix}

with ``severity`` one of ``error`` / ``warning`` / ``info``. The viewer's
Check panel reads them from ``show_dag(obj)["checks"]``.

A library adds its own checks to any Part or Assembly class with the
``__checks__`` hook::

    class PrintedBracket(Part):
        def __checks__(self):
            if self.wall < 0.8:
                return [issue("warning", "printability.wall",
                              f"wall {self.wall} mm < 0.8 mm", fix="thicken it")]
            return []

``__checks__()`` may return issue dicts, :class:`Report` objects or plain
strings (a warning each); missing keys are filled in, and ``components``
defaults to the component's path in the tree. Code that is not a method
(an ``@operation``, a mate rule) attaches findings with :func:`add_check`
or :meth:`Report.attach`.

:func:`collect_checks` walks a Part / Assembly recursively (sub-assemblies
included) and returns every issue; ``part.check()`` and
``assembly.check()`` use it, and so does ``show_dag``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

__all__ = [
    "SEVERITIES",
    "Report",
    "add_check",
    "attached_checks",
    "collect_checks",
    "issue",
    "normalize_issue",
    "own_checks",
]

SEVERITIES = ("error", "warning", "info")
_ATTACHED_ATTR = "_attached_checks"


def issue(
    severity: str,
    code: str,
    message: str,
    components: Iterable[str] = (),
    interfaces: Iterable[str] = (),
    delta: Optional[Dict[str, Any]] = None,
    fix: Optional[str] = None,
) -> Dict[str, Any]:
    """One check issue, in the shape ``Assembly.check()`` returns."""
    if severity not in SEVERITIES:
        raise ValueError(f"issue: severity {severity!r} not in {SEVERITIES}")
    return {
        "severity": severity,
        "code": code,
        "interfaces": list(interfaces),
        "components": list(components),
        "delta": delta,
        "message": message,
        "fix": fix,
    }


@dataclass
class Report:
    """A structured result next to the geometry: what an ``@operation``
    (fits, screening, sizing) or a ``__checks__`` hook found.

    ``data`` is free-form (numbers for a table); ``issues`` are check
    issues. ``report.attach(component)`` makes the issues part of that
    component's ``check()`` and of the DAG ``checks``.
    """

    title: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    issues: List[Dict[str, Any]] = field(default_factory=list)

    def add(self, severity: str, code: str, message: str, **kwargs: Any) -> "Report":
        self.issues.append(issue(severity, code, message, **kwargs))
        return self

    @property
    def ok(self) -> bool:
        return not any(i["severity"] == "error" for i in self.issues)

    def attach(self, component: Any) -> "Report":
        add_check(component, self)
        return self

    def to_json(self) -> Dict[str, Any]:
        return {"title": self.title, "data": dict(self.data), "issues": self.issues}


def _source(obj: Any) -> Any:
    from .compute_functions import _SOURCE_COMPONENT_ATTR

    return getattr(obj, _SOURCE_COMPONENT_ATTR, None) or obj


def add_check(component: Any, found: Any) -> None:
    """Attach an issue (dict / string) or a :class:`Report` to ``component``
    (a Part, an Assembly or their placed root)."""
    target = _source(component)
    bucket = target.__dict__.get(_ATTACHED_ATTR)
    if bucket is None:
        bucket = []
        object.__setattr__(target, _ATTACHED_ATTR, bucket)
    bucket.append(found)


def attached_checks(component: Any) -> List[Any]:
    return list(_source(component).__dict__.get(_ATTACHED_ATTR) or [])


def normalize_issue(found: Any, label: Optional[str] = None) -> List[Dict[str, Any]]:
    """Issues from what a hook returned (dict, string, Report, or a list of
    them), with defaults filled and ``components`` set to ``label`` when the
    hook left it empty."""
    if found is None:
        return []
    if isinstance(found, Report):
        return [i for x in found.issues for i in normalize_issue(x, label)]
    if isinstance(found, (list, tuple)):
        return [i for x in found for i in normalize_issue(x, label)]
    if isinstance(found, str):
        found = {"message": found}
    if not isinstance(found, dict):
        message = str(found)
        found = {
            "message": message,
            "code": getattr(found, "kind", None) or "check",
        }
    out = issue(
        found.get("severity") or "warning",
        found.get("code") or "check",
        found.get("message") or "",
        found.get("components") or ([label] if label else []),
        found.get("interfaces") or (),
        found.get("delta"),
        found.get("fix"),
    )
    for key, value in found.items():  # keep library extras (data, rule…)
        out.setdefault(key, value)
    return [out]


def own_checks(component: Any, label: Optional[str] = None) -> List[Dict[str, Any]]:
    """``component``'s own ``__checks__()`` plus what was attached to it."""
    target = _source(component)
    label = label or target.name.value
    found: List[Dict[str, Any]] = []
    hook = getattr(target, "__checks__", None)
    if callable(hook):
        found += normalize_issue(hook(), label)
    for item in attached_checks(target):
        found += normalize_issue(item, label)
    return found


def collect_checks(obj: Any, interference: bool = False) -> List[Dict[str, Any]]:
    """Every issue of ``obj`` and of everything under it: interface checks
    of each (sub-)assembly built with ``connect`` / ``ground``,
    ``__checks__`` hooks and attached reports of every part and assembly.
    Sub-assembly issues name their components by path (``sub/part``)."""
    return _collect(obj, None, interference, True)


def part_check(self: Any) -> List[Dict[str, Any]]:
    """``part.check()``: the part's ``__checks__`` and attached reports."""
    return collect_checks(self)


def _collect(
    obj: Any, label: Optional[str], interference: bool, with_interfaces: bool
) -> List[Dict[str, Any]]:
    from .gen.models import Assembly, AssemblyRoot

    source = _source(obj)
    found: List[Dict[str, Any]] = []
    if isinstance(source, Assembly):
        from .interfaces.connect import interface_issues, uses_interfaces

        if with_interfaces and uses_interfaces(source):
            prefix = f"{label}/" if label else ""
            for i in interface_issues(source, interference=interference):
                i["components"] = [prefix + c for c in i["components"]]
                found.append(i)
    found += own_checks(source, label)
    if isinstance(source, Assembly) or isinstance(obj, AssemblyRoot):
        from .interference import _display_names

        children = list(source.components)
        for child, name in zip(children, _display_names(children)):
            path = f"{label}/{name}" if label else name
            found += _collect(child, path, False, True)
    return found
