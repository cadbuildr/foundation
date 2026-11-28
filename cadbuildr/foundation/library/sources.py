"""Library sources on the Python ecosystem: PEP 621 dependencies + uv.

No custom package system: a project's code plus its ``pyproject.toml`` are the
state. A library is any installed distribution that declares the entry point
group ``cadbuildr.libraries`` (``name = "import.root"``)::

    [project.entry-points."cadbuildr.libraries"]
    stdlib = "cadbuildr.stdlib"

A project depends on libraries like on any package: ``[project] dependencies``
(PEP 508) plus ``[tool.uv.sources]`` for non-release sources (``git`` +
``branch`` / ``rev`` / ``tag``, ``path`` + ``editable``). ``uv.lock`` is the
lock, ``uv sync`` the install, and every change goes through ``uv add`` /
``uv remove`` / ``uv lock --upgrade-package`` (this module shells out to uv).

Multi-platform rule: a local folder must be a git repository with a remote,
written as a marker-split pair (desktop / cloud use the folder, Pyodide the
git half, which uv.lock pins to a sha)::

    my-parts = [
        { path = "../my-parts", editable = true, marker = "sys_platform != 'emscripten'" },
        { git = "https://github.com/me/parts", branch = "main", marker = "sys_platform == 'emscripten'" },
    ]

Runtimes (``CADBUILDR_RUNTIME``): ``desktop`` runs ``uv sync`` (editable
folder, hot reload by :func:`purge`); ``cloud`` treats the git half as
authoritative (``uv sync --no-install-package`` + ``uv pip install`` of the
locked sha); ``web`` (Pyodide) reads the git sha from uv.lock and fetches that
archive (GitHub codeload or ``CADBUILDR_GITHUB_ARCHIVE_URL``).
"""

from __future__ import annotations

import io
import json
import importlib
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:  # Python 3.11+
    import tomllib as _toml
except ImportError:  # pragma: no cover - 3.10
    try:
        import tomli as _toml  # type: ignore[no-redef]
    except ImportError:
        _toml = None  # type: ignore[assignment]

__all__ = [
    "ENTRY_POINT_GROUP",
    "SourceError",
    "activate",
    "insert",
    "library_entry_points",
    "list_sources",
    "purge",
    "push_source",
    "read_project",
    "read_uv_lock",
    "runtime",
    "set_source",
    "source_of",
    "source_string",
    "sync_sources",
    "update_source",
    "web_plan",
]

ENTRY_POINT_GROUP = "cadbuildr.libraries"
RUNTIME_ENV = "CADBUILDR_RUNTIME"
ARCHIVE_ENV = "CADBUILDR_GITHUB_ARCHIVE_URL"
CACHE_ENV = "CADBUILDR_LIBRARY_CACHE"
WEB_MARKER = "sys_platform == 'emscripten'"
LOCAL_MARKER = "sys_platform != 'emscripten'"
_GITHUB = re.compile(
    r"^(?:https?://|git@)github\.com[/:]([^/]+)/([^/?#]+?)(?:\.git)?/?$"
)


class SourceError(RuntimeError):
    pass


def runtime() -> str:
    """``desktop`` (default), ``web`` or ``cloud``."""
    return (os.environ.get(RUNTIME_ENV) or "desktop").strip().lower()


def normalize(name: str) -> str:
    """PEP 503 name: ``Cadbuildr_Stdlib`` -> ``cadbuildr-stdlib``."""
    return re.sub(r"[-_.]+", "-", name).lower()


# --------------------------------------------------------------------------- #
# Installed libraries (entry points)
# --------------------------------------------------------------------------- #

_EP_CACHE: Optional[Dict[str, Dict[str, Any]]] = None
_SOURCE_CACHE: Dict[str, Optional[str]] = {}
# Import roots purge() reloads (editable folders, branch git sources).
_LIVE: Dict[str, str] = {}
# What activate() loaded itself (web archives): import_root -> source string.
_LOADED_SOURCES: Dict[str, str] = {}


def library_entry_points(refresh: bool = False) -> Dict[str, Dict[str, Any]]:
    """``{import_root: {"id", "import_root", "dist", "version"}}`` of the
    installed ``cadbuildr.libraries`` entry points."""
    global _EP_CACHE
    if _EP_CACHE is None or refresh:
        from importlib import metadata

        out: Dict[str, Dict[str, Any]] = {}
        try:
            eps = metadata.entry_points(group=ENTRY_POINT_GROUP)
        except TypeError:  # pragma: no cover - 3.9 API
            eps = metadata.entry_points().get(ENTRY_POINT_GROUP, [])  # type: ignore[attr-defined]
        for ep in eps:
            dist = getattr(ep, "dist", None)
            out[ep.value] = {
                "id": ep.name,
                "import_root": ep.value,
                "dist": normalize(dist.metadata["Name"]) if dist is not None else None,
                "version": dist.version if dist is not None else None,
            }
        _EP_CACHE = out
    return _EP_CACHE


def library_id_for_root(import_root: str) -> Optional[str]:
    info = library_entry_points().get(import_root)
    return info["id"] if info else None


def _dist_for_root(import_root: str) -> Any:
    from importlib import metadata

    info = library_entry_points().get(import_root)
    if info and info.get("dist"):
        try:
            return metadata.distribution(info["dist"])
        except metadata.PackageNotFoundError:
            pass
    names = [import_root.replace(".", "-").replace("_", "-")]
    try:
        names += metadata.packages_distributions().get(import_root.split(".")[0], [])
    except Exception:  # pragma: no cover
        pass
    rel = import_root.replace(".", "/")
    module_dir = _module_dir(sys.modules.get(import_root))
    for name in dict.fromkeys(names):
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            continue
        editable = _editable_dir(dist)
        if any(str(f).startswith(rel) for f in dist.files or []) or (
            editable
            and module_dir
            and module_dir.startswith(os.path.realpath(editable))
        ):
            return dist
    return None


def _editable_dir(dist: Any) -> Optional[str]:
    try:
        text = dist.read_text("direct_url.json")
    except Exception:
        return None
    if not text:
        return None
    info = json.loads(text)
    url = info.get("url", "")
    if info.get("dir_info", {}).get("editable") and url.startswith("file://"):
        return urllib.request.url2pathname(url[len("file://") :])
    return None


# --------------------------------------------------------------------------- #
# What was loaded: library.source
# --------------------------------------------------------------------------- #


def source_string(import_root: str) -> Optional[str]:
    """``release 0.4.0`` | ``git <url>@<sha>[ dirty]`` | ``local <path>[ dirty]``.

    An editable checkout that is a git repository with a remote reports
    ``git <remote>@<HEAD>[ dirty]``, so a model opened anywhere says which
    library code built it."""
    if import_root in _LOADED_SOURCES:
        return _LOADED_SOURCES[import_root]
    if import_root not in _SOURCE_CACHE:
        _SOURCE_CACHE[import_root] = _installed_source(import_root)
    return _SOURCE_CACHE[import_root]


def _installed_source(import_root: str) -> Optional[str]:
    if import_root == "__main__":
        return None
    try:
        dist = _dist_for_root(import_root)
    except Exception:
        dist = None
    if dist is None:
        folder = _module_dir(sys.modules.get(import_root))
        return _folder_source(folder) if folder else None
    editable = _editable_dir(dist)
    if editable:
        return _folder_source(editable)
    try:
        direct = dist.read_text("direct_url.json")
        if direct:
            info = json.loads(direct)
            vcs = info.get("vcs_info")
            if vcs:
                return f"git {info.get('url')}@{vcs.get('commit_id')}"
    except Exception:
        pass
    return f"release {dist.version}"


def _module_dir(module: Any) -> Optional[str]:
    file = getattr(module, "__file__", None) if module is not None else None
    return str(Path(file).resolve().parent) if file else None


def _folder_source(folder: str) -> str:
    state = local_state(folder)
    suffix = " dirty" if state["dirty"] else ""
    if state["git"] and state["rev"]:
        return f"git {state['git']}@{state['rev']}{suffix}"
    return f"local {folder}{suffix}"


def source_of(import_root: str) -> Optional[Dict[str, Any]]:
    """The manifest's ``library.source`` object."""
    text = source_string(import_root)
    if text is None:
        return None
    kind, _, rest = text.partition(" ")
    dirty = rest.endswith(" dirty")
    rest = rest[: -len(" dirty")] if dirty else rest
    out: Dict[str, Any] = {"source": text}
    if kind == "release":
        out.update(kind="version", version=rest)
    elif kind == "git":
        url, _, sha = rest.rpartition("@")
        out.update(kind="git", git=url, rev=sha, dirty=dirty)
    else:
        out.update(kind="path", path=rest, dirty=dirty)
    return out


# --------------------------------------------------------------------------- #
# pyproject.toml and uv.lock
# --------------------------------------------------------------------------- #


def _load_toml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    if _toml is None:  # pragma: no cover
        raise SourceError("reading TOML needs Python 3.11+ or tomli")
    with open(path, "rb") as fh:
        return _toml.load(fh)


_REQ_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def read_project(project_dir: os.PathLike | str) -> Dict[str, Any]:
    """``{"name", "dependencies": {name: requirement}, "sources": {name: entry | [entries]},
    "entry_points": {id: import_root}}`` of a pyproject.toml."""
    data = _load_toml(Path(project_dir) / "pyproject.toml")
    project = data.get("project", {})
    deps: Dict[str, str] = {}
    for req in project.get("dependencies", []) or []:
        m = _REQ_NAME.match(req)
        if m:
            deps.setdefault(normalize(m.group(1)), req)
    sources = {
        normalize(k): v
        for k, v in data.get("tool", {}).get("uv", {}).get("sources", {}).items()
    }
    return {
        "name": project.get("name"),
        "dependencies": deps,
        "sources": sources,
        "entry_points": project.get("entry-points", {}).get(ENTRY_POINT_GROUP, {}),
    }


def _parse_git_source(text: str) -> Dict[str, Any]:
    """``url?branch=main#sha`` -> {"git", "branch"|"rev"|"tag", "sha"}."""
    base, _, sha = text.partition("#")
    url, _, query = base.partition("?")
    out: Dict[str, Any] = {"git": url, "sha": sha or None}
    for part in query.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k] = v
    return out


def read_uv_lock(project_dir: os.PathLike | str) -> Dict[str, List[Dict[str, Any]]]:
    """``{name: [{"kind": "git"|"editable"|"registry"|..., "version", "git", "sha", "path"...}]}``."""
    data = _load_toml(Path(project_dir) / "uv.lock")
    out: Dict[str, List[Dict[str, Any]]] = {}
    for pkg in data.get("package", []):
        source = pkg.get("source", {})
        entry: Dict[str, Any] = {"version": pkg.get("version")}
        if "git" in source:
            entry.update(kind="git", **_parse_git_source(source["git"]))
        elif "editable" in source:
            entry.update(kind="editable", path=source["editable"])
        elif "directory" in source:
            entry.update(kind="directory", path=source["directory"])
        elif "registry" in source:
            entry.update(kind="registry")
        else:
            entry.update(kind=next(iter(source), "unknown"))
        out.setdefault(normalize(pkg.get("name", "")), []).append(entry)
    return out


def _describe_source(source: Any) -> Dict[str, Any]:
    """Kind and fields of a ``[tool.uv.sources]`` value (pair-aware)."""
    if source is None:
        entries: List[Dict[str, Any]] = []
    else:
        entries = [dict(s) for s in (source if isinstance(source, list) else [source])]
    path = next((e for e in entries if "path" in e), None)
    git = next((e for e in entries if "git" in e), None)
    out: Dict[str, Any] = {"kind": "version"}
    if path is not None:
        out.update(kind="path", path=path["path"], editable=bool(path.get("editable")))
        out["desktop_only"] = git is None
    elif git is not None:
        out["kind"] = "git"
    elif entries:
        out["kind"] = next(iter(entries[0]))
    if git is not None:
        out["git"] = git["git"]
        for key in ("branch", "rev", "tag"):
            if git.get(key):
                out[key] = git[key]
    return out


# --------------------------------------------------------------------------- #
# git and uv
# --------------------------------------------------------------------------- #


def _run(
    cmd: List[str], cwd: Optional[os.PathLike | str] = None, check: bool = True
) -> str:
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except FileNotFoundError as exc:
        raise SourceError(f"{cmd[0]} is not installed") from exc
    if check and proc.returncode != 0:
        lines = [
            m
            for m in (proc.stderr or proc.stdout).strip().splitlines()
            if "UV_NATIVE_TLS" not in m
        ]
        raise SourceError(f"{' '.join(cmd[1:3])}: {' '.join(lines[-4:])}")
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _git(
    *args: str, cwd: Optional[os.PathLike | str] = None, check: bool = True
) -> str:
    return _run(["git", *args], cwd=cwd, check=check)


def _uv(*args: str, cwd: os.PathLike | str) -> str:
    uv = os.environ.get("CADBUILDR_UV") or shutil.which("uv") or "uv"
    return _run([uv, *args], cwd=cwd)


def local_state(path: os.PathLike | str) -> Dict[str, Any]:
    """HEAD sha, dirty, unpushed commits, origin url and branch of a checkout."""
    path = str(path)
    empty = {"rev": None, "dirty": False, "unpushed": 0, "git": None, "branch": None}
    if not os.path.isdir(path) or not _git(
        "rev-parse", "--is-inside-work-tree", cwd=path, check=False
    ):
        return empty
    head = _git("rev-parse", "HEAD", cwd=path, check=False) or None
    branch = _git("rev-parse", "--abbrev-ref", "HEAD", cwd=path, check=False) or None
    remote = _git("remote", "get-url", "origin", cwd=path, check=False) or None
    dirty = bool(_git("status", "--porcelain", cwd=path, check=False))
    unpushed = 0
    if head:
        args = ["rev-list", "--count", "HEAD"] + (
            ["--not", "--remotes=origin"] if remote else []
        )
        unpushed = int(_git(*args, cwd=path, check=False) or 0)
    return {
        "rev": head,
        "dirty": dirty,
        "unpushed": unpushed,
        "git": remote,
        "branch": None if branch == "HEAD" else branch,
    }


def _on_remote(path: str, sha: Optional[str]) -> bool:
    return bool(sha) and bool(
        _git("branch", "-r", "--contains", str(sha), cwd=path, check=False)
    )


def _remote_has(url: str, sha: str) -> bool:
    """Does the remote have ``sha``? (fetch exactly that object into a scratch repo)."""
    tmp = tempfile.mkdtemp(prefix="cadbuildr-rev-")
    try:
        _git("init", "-q", "--bare", tmp)
        _git("fetch", "-q", "--depth", "1", url, sha, cwd=tmp, check=False)
        return bool(_git("cat-file", "-t", sha, cwd=tmp, check=False))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------- #
# Status (sources list)
# --------------------------------------------------------------------------- #


def _is_library(name: str, sources: Dict[str, Any]) -> bool:
    if name in sources or name.startswith("cadbuildr-"):
        return True
    return any(info.get("dist") == name for info in library_entry_points().values())


def _library_id(name: str, folder: Optional[Path] = None) -> str:
    for info in library_entry_points().values():
        if info.get("dist") == name:
            return info["id"]
    if folder is not None and (folder / "pyproject.toml").exists():
        eps = read_project(folder).get("entry_points") or {}
        if eps:
            return next(iter(eps))
    return name


def _resolve_name(project: Path, name: str) -> str:
    """A library id (``woodworking``) or a distribution name -> the distribution name."""
    n = normalize(name)
    proj = read_project(project)
    if n in proj["dependencies"]:
        return n
    for info in library_entry_points().values():
        if info["id"] == name and info.get("dist"):
            return info["dist"]
    for dep, source in proj["sources"].items():
        desc = _describe_source(source)
        if (
            desc.get("path")
            and _library_id(dep, (project / desc["path"]).resolve()) == name
        ):
            return dep
    return n


def _status(project: Path, name: str, remote: bool = False) -> Dict[str, Any]:
    proj = read_project(project)
    desc = _describe_source(proj["sources"].get(name))
    locked = read_uv_lock(project).get(name, [])
    git_lock = next((e for e in locked if e["kind"] == "git"), None)
    version_lock = next((e.get("version") for e in locked), None)
    folder = (project / desc["path"]).resolve() if desc.get("path") else None
    requirement = proj["dependencies"].get(name)
    row: Dict[str, Any] = {
        "id": _library_id(name, folder),
        "name": name,
        "requirement": requirement,
        "kind": desc["kind"],
        "ref": desc.get("rev")
        or desc.get("tag")
        or desc.get("branch")
        or desc.get("path")
        or ((requirement or "")[len(name) :].strip() or None),
        "git": desc.get("git"),
        "branch": desc.get("branch"),
        "path": desc.get("path"),
        "version": version_lock,
        "locked": git_lock["sha"] if git_lock else version_lock,
        "rev": git_lock["sha"] if git_lock else None,
        "behind": None,
        "dirty": False,
        "unpushed": 0,
        "drift": [],
        "desktop_only": bool(desc.get("desktop_only")),
        "error": None,
    }
    if folder is not None:
        if not folder.is_dir():
            row["error"] = f"local folder {folder} not found"
            return row
        if remote and row["git"]:
            _git("fetch", "-q", "origin", cwd=folder, check=False)
        state = local_state(folder)
        row.update(rev=state["rev"], dirty=state["dirty"], unpushed=state["unpushed"])
        if state["dirty"]:
            row["drift"].append("dirty")
        if state["unpushed"]:
            row["drift"].append("unpushed")
        if row["git"] and row["locked"] and not _on_remote(str(folder), row["locked"]):
            row["drift"].append("rev_not_on_remote")
        if remote and row["git"] and row["locked"] and row["branch"]:
            count = _git(
                "rev-list",
                "--count",
                f"{row['locked']}..origin/{row['branch']}",
                cwd=folder,
                check=False,
            )
            row["behind"] = int(count) if count else None
        if row["desktop_only"]:
            row["warnings"] = [
                f"{name}: desktop-only local library (no git remote: not on web / cloud)"
            ]
    elif remote and row["kind"] == "git" and row["branch"] and row["locked"]:
        head = _git(
            "ls-remote", str(row["git"]), f"refs/heads/{row['branch']}", check=False
        )
        if head:
            row["head"] = head.split()[0]
            row["behind"] = 0 if row["head"] == row["locked"] else None
    return row


def list_sources(
    project_dir: os.PathLike | str, remote: bool = False
) -> List[Dict[str, Any]]:
    """Status of each library dependency: kind, ref, locked sha, behind, drift."""
    project = Path(project_dir).resolve()
    proj = read_project(project)
    return [
        _status(project, name, remote)
        for name in proj["dependencies"]
        if _is_library(name, proj["sources"])
    ]


def _status_ok(project: Path, name: str) -> Dict[str, Any]:
    return {"ok": True, **_status(project, name)}


# --------------------------------------------------------------------------- #
# Commands (sources set / update / push / sync)
# --------------------------------------------------------------------------- #

_TABLE_HEADER = re.compile(r"^\[[A-Za-z\"]")


def _write_uv_source(project: Path, name: str, value: str) -> None:
    """Replace ``name = ...`` (possibly a multi-line list) in ``[tool.uv.sources]``.

    Used only for what uv has no flag for: the marker-split pair."""
    path = project / "pyproject.toml"
    lines = path.read_text().splitlines()
    start = next(
        (
            i
            for i, l in enumerate(lines)
            if re.match(r"^\[\s*tool\.uv\.sources\s*\]\s*$", l)
        ),
        None,
    )
    if start is None:
        lines += ["", "[tool.uv.sources]", f"{name} = {value}"]
    else:
        key = re.compile(r"^\"?([A-Za-z0-9._-]+)\"?\s*=")
        found = None
        i = start + 1
        while i < len(lines) and not _TABLE_HEADER.match(lines[i]):
            m = key.match(lines[i])
            if m and normalize(m.group(1)) == normalize(name):
                found = i
                break
            i += 1
        if found is None:
            lines.insert(start + 1, f"{name} = {value}")
        else:

            def balance(text: str) -> int:
                return (
                    text.count("[")
                    + text.count("{")
                    - text.count("]")
                    - text.count("}")
                )

            end, depth = found, balance(lines[found].split("=", 1)[1])
            while depth > 0 and end + 1 < len(lines):
                end += 1
                depth += balance(lines[end])
            lines[found : end + 1] = [
                f"{lines[found].split('=', 1)[0].rstrip()} = {value}"
            ]
    path.write_text("\n".join(lines) + "\n")


def _pair(path: str, git: str, branch: Optional[str]) -> str:
    return (
        "[\n"
        f'    {{ path = "{path}", editable = true, marker = "{LOCAL_MARKER}" }},\n'
        f'    {{ git = "{git}", branch = "{branch or "main"}", marker = "{WEB_MARKER}" }},\n'
        "]"
    )


def set_source(
    project_dir: os.PathLike | str,
    name: str,
    spec: Optional[Dict[str, Any]],
    sync: bool = True,
) -> Dict[str, Any]:
    """Point a library dependency at a source (``uv add`` / ``uv remove``).

    ``spec``: ``{"version": ">=0.4"}`` | ``{"git", "branch"|"rev"|"tag"}`` |
    ``{"path", "desktop_only"?, "branch"?}`` (written as the path / git pair)
    | ``None`` (remove)."""
    project = Path(project_dir).resolve()
    dist = _resolve_name(project, name)
    present = dist in read_project(project)["dependencies"]
    if spec is None:
        if not present:
            raise SourceError(f"{name!r} is not a dependency of {project}")
        _uv("remove", "--no-sync", dist, cwd=project)
        if sync:
            sync_sources(project)
        return {"ok": True, "name": dist, "removed": True}

    if spec.get("path"):
        folder = (project / str(spec["path"])).resolve()
        if not (folder / "pyproject.toml").exists():
            raise SourceError(f"{folder} is not a Python project (no pyproject.toml)")
        dist = normalize(read_project(folder).get("name") or dist)
        state = local_state(folder)
        git = spec.get("git") or state["git"]
        if not git and not spec.get("desktop_only"):
            raise SourceError(
                f"{folder} has no git remote: push it to a repository (git remote add origin ...) "
                "or add it with desktop_only (it will not load on the web / in the cloud)"
            )
        rel = os.path.relpath(folder, project)
        if dist in read_project(project)["dependencies"]:
            _uv("remove", "--no-sync", dist, cwd=project)
        _uv("add", "--no-sync", "--editable", rel, cwd=project)
        if git:
            _write_uv_source(
                project, dist, _pair(rel, git, spec.get("branch") or state["branch"])
            )
            _uv("lock", cwd=project)
    else:
        if present:
            _uv("remove", "--no-sync", dist, cwd=project)
        if spec.get("git"):
            args = ["add", "--no-sync", f"{dist} @ git+{spec['git']}"]
            for key in ("branch", "rev", "tag"):
                if spec.get(key):
                    args += [f"--{key}", str(spec[key])]
            _uv(*args, cwd=project)
        else:
            version = str(spec.get("version") or "").strip()
            if version == "*":
                version = ""
            elif version and version[0].isdigit():
                version = f"=={version}"
            _uv("add", "--no-sync", f"{dist}{version}", cwd=project)
    if sync:
        sync_sources(project)
    return _status_ok(project, dist)


def update_source(
    project_dir: os.PathLike | str, name: str, sync: bool = True
) -> Dict[str, Any]:
    """Re-resolve a library (a branch to its head): ``uv lock --upgrade-package``."""
    project = Path(project_dir).resolve()
    dist = _resolve_name(project, name)
    if dist not in read_project(project)["dependencies"]:
        raise SourceError(f"unknown library {name!r}")
    _uv("lock", "--upgrade-package", dist, cwd=project)
    if sync:
        sync_sources(project)
    return _status_ok(project, dist)


def push_source(
    project_dir: os.PathLike | str, name: str, sync: bool = True
) -> Dict[str, Any]:
    """``git push`` a local library's checkout, then lock the pushed sha."""
    project = Path(project_dir).resolve()
    dist = _resolve_name(project, name)
    desc = _describe_source(read_project(project)["sources"].get(dist))
    if not desc.get("path"):
        raise SourceError(f"{name!r} is not a local library")
    folder = (project / desc["path"]).resolve()
    state = local_state(folder)
    if not state["git"]:
        raise SourceError(f"{folder} has no git remote")
    branch = desc.get("branch") or state["branch"] or "main"
    _git("push", "-q", "origin", f"HEAD:refs/heads/{branch}", cwd=folder)
    _git("fetch", "-q", "origin", cwd=folder, check=False)
    _uv("lock", "--upgrade-package", dist, cwd=project)
    if sync:
        sync_sources(project)
    return _status_ok(project, dist)


def _venv_python(project: Path) -> Path:
    venv = Path(os.environ.get("UV_PROJECT_ENVIRONMENT") or project / ".venv")
    if not venv.is_absolute():
        venv = project / venv
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def sync_sources(
    project_dir: os.PathLike | str, runtime_name: Optional[str] = None
) -> Dict[str, Any]:
    """Install what uv.lock names, for this runtime.

    ``desktop``: ``uv sync``. ``cloud``: the git half of each local library is
    authoritative (the folder is not there): ``uv sync --frozen
    --no-install-package <lib>`` then ``uv pip install <lib> @ git+<url>@<sha>``
    (the branch head, with a warning, when the remote lacks the locked sha).
    ``web``: nothing to install; returns :func:`web_plan`."""
    project = Path(project_dir).resolve()
    rt = (runtime_name or runtime()).lower()
    report: Dict[str, Any] = {
        "ok": True,
        "runtime": rt,
        "installed": [],
        "warnings": [],
    }
    if rt == "web":
        report["plan"] = web_plan(project)
        return report
    if rt != "cloud":
        _uv("sync", cwd=project)
        return report
    proj = read_project(project)
    lock = read_uv_lock(project)
    pairs = []
    for name, source in proj["sources"].items():
        if _describe_source(source)["kind"] != "path":
            continue
        git_lock = next((e for e in lock.get(name, []) if e["kind"] == "git"), None)
        if git_lock is None:
            report["warnings"].append(
                f"{name}: desktop-only local library, not installed in the cloud"
            )
            continue
        pairs.append((name, git_lock))
    args = ["sync", "--frozen"]
    for name, _ in pairs:
        args += ["--no-install-package", name]
    _uv(*args, cwd=project)
    for name, git_lock in pairs:
        sha = git_lock["sha"]
        if _remote_has(git_lock["git"], sha):
            target = f"{name} @ git+{git_lock['git']}@{sha}"
        else:
            ref = git_lock.get("branch")
            report["warnings"].append(
                f"{name}: built with unpushed library changes? {sha[:12]} is not on {git_lock['git']}; "
                f"using {ref or 'the default branch'} head"
            )
            target = f"{name} @ git+{git_lock['git']}" + (f"@{ref}" if ref else "")
        _uv(
            "pip",
            "install",
            "--no-deps",
            "--python",
            str(_venv_python(project)),
            target,
            cwd=project,
        )
        report["installed"].append(target)
    return report


# --------------------------------------------------------------------------- #
# insert: the code sync's import + call for a library item
# --------------------------------------------------------------------------- #


def _py_literal(value: Any) -> str:
    import enum

    if isinstance(value, enum.Enum):
        return f"{type(value).__name__}.{value.name}"
    if isinstance(value, str):
        return json.dumps(value)
    return repr(value)


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower().replace("__", "_")


def _import_line(item: Any) -> str:
    """Shortest public import: the library root when it re-exports the class."""
    top = item.cls.split(".")[0]
    root = item.import_root
    try:
        if getattr(importlib.import_module(root), top, None) is getattr(
            importlib.import_module(item.module), top
        ):
            return f"from {root} import {top}"
    except Exception:
        pass
    return f"from {item.module} import {top}"


def insert(
    item_id: str,
    inputs: Optional[Dict[str, Any]] = None,
    var: Optional[str] = None,
    project_dir: Optional[os.PathLike | str] = None,
    ensure_dependency: bool = True,
    connect: Optional[Dict[str, Any]] = None,
    connect_given: Optional[bool] = None,
    assembly: str = "assembly",
) -> Dict[str, Any]:
    """``{"ok", "import": "from m import Cls", "code": "cls_1 = Cls(a=1)", "var", "dependency"}``.

    With ``connect`` (``{"own": "<interface>", "target": ["<var>", "<interface>"],
    "dof": {...}}``) the result also has ``connect`` -- the
    ``assembly.connect(...)`` line (``assembly.ground(var)`` when ``target`` is
    null, or ``connect`` itself is None with ``connect_given``) -- and ``lines``
    (constructor then connect).

    With a project, the item's distribution is added with ``uv add`` when the
    project does not depend on it yet."""
    from .evaluate import resolve_item

    item = resolve_item(item_id)
    call_args = (
        dict(inputs or {})
        if item.kind == "operation"
        else item.coerce_inputs(dict(inputs or {}))
    )
    name = var or f"{_snake(item.cls.split('.')[-1])}_1"
    args = ", ".join(f"{k}={_py_literal(v)}" for k, v in call_args.items())
    out: Dict[str, Any] = {
        "ok": True,
        "item": item.id,
        "import": _import_line(item),
        "code": f"{name} = {item.cls}({args})",
        "var": name,
        "dependency": None,
    }
    if connect is not None or connect_given:
        from .mating import connect_line

        spec = connect or {}
        out["connect"] = connect_line(
            name, spec.get("own"), spec.get("target"), spec.get("dof"), assembly
        )
        out["lines"] = [out["code"], out["connect"]]
    if project_dir is not None and ensure_dependency:
        project = Path(project_dir).resolve()
        info = library_entry_points().get(item.import_root) or {}
        dist = info.get("dist")
        if dist is None:
            found = _dist_for_root(item.import_root)
            dist = normalize(found.metadata["Name"]) if found is not None else None
        if dist:
            proj = read_project(project)
            dep: Dict[str, Any] = {"name": dist, "added": False}
            if (
                dist != normalize(proj.get("name") or "")
                and dist not in proj["dependencies"]
            ):
                try:
                    _uv("add", dist, cwd=project)
                    dep["added"] = True
                except SourceError as exc:
                    dep["error"] = str(exc)
            out["dependency"] = dep
    return out


# --------------------------------------------------------------------------- #
# Runtimes: activate / purge (hot reload) / web archives
# --------------------------------------------------------------------------- #


def cache_root() -> Path:
    env = os.environ.get(CACHE_ENV)
    if env:
        return Path(env)
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(
        os.path.expanduser("~"), ".cache"
    )
    return Path(base) / "cadbuildr" / "libraries"


def _github(url: str) -> Optional[Tuple[str, str]]:
    m = _GITHUB.match(url.strip())
    return (m.group(1), m.group(2)) if m else None


def _archive_url(url: str, sha: str) -> Optional[str]:
    gh = _github(url)
    if gh is None:
        return None
    template = os.environ.get(ARCHIVE_ENV)
    if template:
        if "{" in template:
            return template.format(owner=gh[0], repo=gh[1], sha=sha, url=url)
        # A proxy base (the web host): <base>/<owner>/<repo>/<sha>.
        return f"{template.rstrip('/')}/{gh[0]}/{gh[1]}/{sha}"
    return f"https://codeload.github.com/{gh[0]}/{gh[1]}/tar.gz/{sha}"


def _extract(data: bytes, dest: Path) -> None:
    """Extract an archive, dropping its top-level folder (``<repo>-<sha>/``)."""
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tar:
        members = []
        for m in tar.getmembers():
            parts = m.name.split("/", 1)
            if len(parts) < 2 or not parts[1]:
                continue
            m.name = parts[1]
            if m.name.startswith("/") or ".." in Path(m.name).parts:
                continue
            members.append(m)
        kwargs = {"filter": "data"} if hasattr(tarfile, "data_filter") else {}
        tar.extractall(dest, members=members, **kwargs)  # noqa: S202 - filtered above


def download_archive(lib_id: str, url: str, sha: str) -> Path:
    """``<cache>/<id>/<sha>/``: a GitHub repository at ``sha`` (reused if present)."""
    dest = cache_root() / lib_id / sha
    if dest.is_dir():
        return dest
    archive = _archive_url(url, sha)
    if archive is None:
        raise SourceError(f"{url}: only GitHub repositories can be fetched as archives")
    try:
        req = urllib.request.Request(
            archive, headers={"User-Agent": "cadbuildr-library"}
        )
        with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
            data = resp.read()
    except urllib.error.HTTPError as exc:
        raise SourceError(f"{url}@{sha}: archive download failed ({exc.code})") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise SourceError(f"{url}@{sha}: archive download failed ({exc})") from exc
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(dir=dest.parent, prefix=".tmp-"))
    try:
        _extract(data, tmp)
        try:
            tmp.rename(dest)
        except OSError:
            if not dest.is_dir():
                raise
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return dest


def _package_root(root: Path) -> Path:
    if not (root / "pyproject.toml").exists() and root.is_dir():
        children = [p for p in root.iterdir() if not p.name.startswith(".")]
        if len(children) == 1 and children[0].is_dir():
            return children[0]  # extracted with its top-level folder
    return root


def _path_entry(package_dir: Path) -> Path:
    src = package_dir / "src"
    if src.is_dir() and any(p.is_dir() for p in src.iterdir()):
        return src
    return package_dir


def web_plan(project_dir: os.PathLike | str) -> List[Dict[str, Any]]:
    """What Pyodide fetches: the git half of each library, at uv.lock's sha."""
    project = Path(project_dir).resolve()
    proj = read_project(project)
    lock = read_uv_lock(project)
    plan = []
    for name, source in proj["sources"].items():
        if not _describe_source(source).get("git"):
            continue
        git_lock = next((e for e in lock.get(name, []) if e["kind"] == "git"), None)
        if git_lock is None or not git_lock.get("sha"):
            continue
        plan.append(
            {
                "name": name,
                "git": git_lock["git"],
                "sha": git_lock["sha"],
                "archive": _archive_url(git_lock["git"], git_lock["sha"]),
                "cache": str(cache_root() / name / git_lock["sha"]),
            }
        )
    return plan


def _roots_of_folder(folder: Path) -> List[str]:
    if not (folder / "pyproject.toml").exists():
        return []
    return list((read_project(folder).get("entry_points") or {}).values())


def activate(
    project_dir: os.PathLike | str, runtime_name: Optional[str] = None
) -> Dict[str, Any]:
    """Prepare a run of the project in this runtime.

    Desktop / cloud: the environment is uv's (``uv sync``); this records which
    libraries are live (editable local folders, branch git sources) so
    :func:`purge` reloads them. Web (Pyodide, no uv): fetches each library's
    git half at the locked sha (or reuses ``<cache>/<name>/<sha>/`` prefetched
    by the host) and puts it on ``sys.path``."""
    project = Path(project_dir).resolve()
    rt = (runtime_name or runtime()).lower()
    report: Dict[str, Any] = {"runtime": rt, "libraries": [], "warnings": []}
    proj = read_project(project)
    if rt == "web":
        import importlib

        for entry in web_plan(project):
            try:
                root = _package_root(
                    download_archive(entry["name"], entry["git"], entry["sha"])
                )
            except SourceError as exc:
                report["warnings"].append(str(exc))
                continue
            path_entry = str(_path_entry(root))
            if path_entry not in sys.path:
                sys.path.insert(0, path_entry)
            for import_root in _roots_of_folder(root):
                _LOADED_SOURCES[import_root] = f"git {entry['git']}@{entry['sha']}"
                _drop_modules(import_root)
            report["libraries"].append({**entry, "entry": path_entry})
        importlib.invalidate_caches()
        return report
    for name, source in proj["sources"].items():
        desc = _describe_source(source)
        roots: List[str] = []
        if desc["kind"] == "path":
            roots = _roots_of_folder((project / desc["path"]).resolve())
            if desc.get("desktop_only"):
                report["warnings"].append(
                    f"{name}: desktop-only local library (not portable)"
                )
        elif desc["kind"] == "git" and desc.get("branch"):
            roots = [
                r
                for r, info in library_entry_points().items()
                if info.get("dist") == name
            ]
        for import_root in roots:
            _LIVE[import_root] = name
        report["libraries"].append(
            {
                "name": name,
                "kind": desc["kind"],
                "import_roots": roots,
                "live": bool(roots),
            }
        )
    return report


def _drop_modules(import_root: str, delete_pyc: bool = False) -> List[str]:
    names = [
        n
        for n in list(sys.modules)
        if n == import_root or n.startswith(import_root + ".")
    ]
    for name in names:
        module = sys.modules.pop(name, None)
        cached = getattr(module, "__cached__", None)
        if delete_pyc and cached:
            try:
                os.remove(cached)
            except OSError:
                pass
    try:
        from .registry import forget

        forget(import_root)
    except Exception:  # pragma: no cover
        pass
    return names


def _editable_roots() -> List[str]:
    from importlib import metadata

    out = []
    for import_root, info in library_entry_points().items():
        try:
            if info.get("dist") and _editable_dir(metadata.distribution(info["dist"])):
                out.append(import_root)
        except Exception:
            continue
    return out


def purge(roots: Optional[List[str]] = None) -> List[str]:
    """Drop every module of a live library (activated local folders and
    branches, plus editable installs) so the next run imports the current
    code. Returns the purged module names."""
    import importlib
    import linecache

    targets = (
        list(roots)
        if roots is not None
        else list(dict.fromkeys([*_LIVE, *_editable_roots()]))
    )
    out: List[str] = []
    for import_root in targets:
        out += _drop_modules(import_root)
        _SOURCE_CACHE.pop(import_root, None)
    importlib.invalidate_caches()
    linecache.checkcache()
    return out


def reset() -> None:
    """Forget what was activated (tests)."""
    global _EP_CACHE
    _LIVE.clear()
    _LOADED_SOURCES.clear()
    _SOURCE_CACHE.clear()
    _EP_CACHE = None
