"""cadbuildr.foundation.library.sources on uv: dependencies + [tool.uv.sources],
uv.lock, the path / git marker pair, drift, push, hot reload, runtimes.

Runs real uv offline (UV_OFFLINE=1): remotes are local bare repositories
reached through file:// URLs; the test libraries have no dependencies."""

from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
import sys
import textwrap
import uuid
from pathlib import Path

import pytest

from cadbuildr.foundation.library import sources
from cadbuildr.foundation.library.cli import main as cli_main
from cadbuildr.foundation.library.stamp import stamp_of

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("uv") is None, reason="needs git and uv"
)


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("UV_OFFLINE", "1")
    monkeypatch.setenv(sources.CACHE_ENV, str(tmp_path / "cache"))
    monkeypatch.delenv(sources.RUNTIME_ENV, raising=False)
    monkeypatch.delenv(sources.ARCHIVE_ENV, raising=False)
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    monkeypatch.delenv("UV_PROJECT_ENVIRONMENT", raising=False)
    for key, value in {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
        "GIT_CONFIG_GLOBAL": str(tmp_path / "gitconfig"),
    }.items():
        monkeypatch.setenv(key, value)
    (tmp_path / "gitconfig").write_text("[init]\n\tdefaultBranch = main\n")
    path_before = list(sys.path)
    yield
    sources.reset()
    sys.path[:] = path_before


def git(*args, cwd):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


PART = textwrap.dedent("""
    from cadbuildr.foundation import Part, Sketch, Circle, Point, Extrusion
    from cadbuildr.foundation.library import part, Num

    @part(category="Things")
    class Thing(Part):
        def __init__(self, size: Num(min=1, max=50) = 5):
            self.add_operation(Extrusion(Circle(Point(Sketch(self.xy()), 0, 0), size), 1))
    """)


def make_library(root: Path, pkg: str, value: int) -> Path:
    """A library checkout: PEP 621 project ``<pkg>-dist`` with the
    ``cadbuildr.libraries`` entry point, package ``pkg`` (VALUE + a @part)."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(textwrap.dedent(f"""
            [project]
            name = "{pkg.replace('_', '-')}-dist"
            version = "0.1.0"
            requires-python = ">=3.10"

            [project.entry-points."cadbuildr.libraries"]
            {pkg} = "{pkg}"

            [build-system]
            requires = ["hatchling"]
            build-backend = "hatchling.build"

            [tool.hatch.build.targets.wheel]
            packages = ["{pkg}"]
            """))
    (root / ".gitignore").write_text("__pycache__/\n")
    (root / pkg).mkdir(exist_ok=True)
    set_value(root, pkg, value)
    (root / pkg / "parts.py").write_text(PART)
    return root


def set_value(root: Path, pkg: str, value: int) -> None:
    # A different length too: a same-second, same-size edit could hit a stale .pyc.
    (root / pkg / "__init__.py").write_text(f"VALUE = {value}  # {'x' * value}\n")


def make_remote(tmp_path: Path, pkg: str, value: int) -> tuple[str, Path]:
    """A bare repository (``file://`` URL) and a working clone tracking it."""
    work = make_library(tmp_path / pkg, pkg, value)
    git("init", "-q", "-b", "main", cwd=work)
    git("add", "-A", cwd=work)
    git("commit", "-q", "-m", "init", cwd=work)
    bare = tmp_path / f"{pkg}.git"
    git("clone", "-q", "--bare", str(work), str(bare), cwd=tmp_path)
    url = bare.resolve().as_uri()
    git("remote", "add", "origin", url, cwd=work)
    git("fetch", "-q", "origin", cwd=work)
    git("branch", "-q", "--set-upstream-to=origin/main", "main", cwd=work)
    return url, work


def make_project(tmp_path: Path) -> Path:
    proj = tmp_path / "project"
    proj.mkdir()
    (proj / "pyproject.toml").write_text(
        '[project]\nname = "proj"\nversion = "0.0.1"\nrequires-python = ">=3.10"\ndependencies = []\n'
    )
    return proj


def unique(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def cli(capsys, *args):
    assert cli_main(list(args)) == 0
    out = capsys.readouterr().out
    assert len(out.strip().splitlines()) == 1, out
    return json.loads(out)


# --------------------------------------------------------------------------- #


def test_git_source_branch_then_rev_then_remove(tmp_path, capsys):
    pkg = unique("gitlib")
    dist = f"{pkg.replace('_', '-')}-dist"
    url, work = make_remote(tmp_path, pkg, 1)
    sha1 = git("rev-parse", "HEAD", cwd=work)
    proj = make_project(tmp_path)

    row = cli(
        capsys,
        "sources",
        "--project",
        str(proj),
        "set",
        dist,
        json.dumps({"git": url, "branch": "main"}),
        "--no-sync",
    )
    assert (
        row["ok"]
        and row["kind"] == "git"
        and row["locked"] == sha1
        and row["branch"] == "main"
    )
    project = sources.read_project(proj)
    assert dist in project["dependencies"]
    assert project["sources"][dist] == {"git": url, "branch": "main"}
    assert sources.read_uv_lock(proj)[dist][0]["sha"] == sha1

    # Upstream moves on: the lock keeps sha1 until `update`.
    set_value(work, pkg, 2)
    git("commit", "-qam", "v2", cwd=work)
    git("push", "-q", "origin", "main", cwd=work)
    sha2 = git("rev-parse", "HEAD", cwd=work)
    rows = cli(capsys, "sources", "--project", str(proj), "list", "--remote")
    assert (
        rows[0]["locked"] == sha1
        and rows[0]["head"] == sha2
        and rows[0]["behind"] is None
    )
    row = cli(capsys, "sources", "--project", str(proj), "update", dist, "--no-sync")
    assert row["locked"] == sha2

    row = cli(
        capsys,
        "sources",
        "--project",
        str(proj),
        "set",
        dist,
        json.dumps({"git": url, "rev": sha1[:7]}),
        "--no-sync",
    )
    assert row["locked"] == sha1 and row["ref"] == sha1[:7]
    assert sources.read_project(proj)["sources"][dist] == {"git": url, "rev": sha1[:7]}

    assert cli(
        capsys, "sources", "--project", str(proj), "set", dist, "null", "--no-sync"
    ) == {
        "ok": True,
        "name": dist,
        "removed": True,
    }
    assert sources.read_project(proj)["dependencies"] == {}
    assert sources.read_project(proj)["sources"] == {}

    # Failures: one JSON line, exit 0.
    err = cli(capsys, "sources", "--project", str(proj), "update", "missing")
    assert err == {"ok": False, "error": "unknown library 'missing'"}


def test_path_source_is_written_as_a_marker_pair_with_drift_and_push(tmp_path, capsys):
    pkg = unique("pairlib")
    dist = f"{pkg.replace('_', '-')}-dist"
    url, work = make_remote(tmp_path, pkg, 1)
    pushed = git("rev-parse", "HEAD", cwd=work)
    proj = make_project(tmp_path)

    row = cli(
        capsys,
        "sources",
        "--project",
        str(proj),
        "set",
        pkg,
        json.dumps({"path": f"../{pkg}"}),
        "--no-sync",
    )
    assert row["kind"] == "path" and row["git"] == url and row["branch"] == "main"
    assert row["id"] == pkg and row["name"] == dist
    assert row["locked"] == pushed and row["drift"] == [] and not row["desktop_only"]
    source = sources.read_project(proj)["sources"][dist]
    assert source == [
        {"path": f"../{pkg}", "editable": True, "marker": sources.LOCAL_MARKER},
        {"git": url, "branch": "main", "marker": sources.WEB_MARKER},
    ]
    kinds = sorted(e["kind"] for e in sources.read_uv_lock(proj)[dist])
    assert kinds == ["editable", "git"]

    # Local work: committed but unpushed, plus uncommitted changes.
    set_value(work, pkg, 2)
    git("commit", "-qam", "local v2", cwd=work)
    set_value(work, pkg, 3)
    row = cli(capsys, "sources", "--project", str(proj), "list")[0]
    assert (
        row["drift"] == ["dirty", "unpushed"] and row["unpushed"] == 1 and row["dirty"]
    )
    assert row["rev"] == git("rev-parse", "HEAD", cwd=work) and row["locked"] == pushed

    # A lock naming a sha the remote does not have.
    lock = (proj / "uv.lock").read_text()
    (proj / "uv.lock").write_text(
        lock.replace(pushed, git("rev-parse", "HEAD", cwd=work))
    )
    assert "rev_not_on_remote" in sources.list_sources(proj)[0]["drift"]
    (proj / "uv.lock").write_text(lock)

    # Sync library: push, then the lock follows the pushed sha.
    git("commit", "-qam", "local v3", cwd=work)
    v3 = git("rev-parse", "HEAD", cwd=work)
    row = cli(capsys, "sources", "--project", str(proj), "push", pkg, "--no-sync")
    assert row["ok"] and row["locked"] == v3 and row["rev"] == v3 and row["drift"] == []
    assert git("rev-parse", "main", cwd=tmp_path / f"{pkg}.git") == v3


def test_path_without_remote_is_refused_unless_desktop_only(tmp_path, capsys):
    pkg = unique("noremote")
    dist = f"{pkg.replace('_', '-')}-dist"
    lib = make_library(tmp_path / pkg, pkg, 1)
    git("init", "-q", "-b", "main", cwd=lib)
    proj = make_project(tmp_path)
    err = cli(
        capsys,
        "sources",
        "--project",
        str(proj),
        "set",
        dist,
        json.dumps({"path": f"../{pkg}"}),
        "--no-sync",
    )
    assert err["ok"] is False and "no git remote" in err["error"]
    row = cli(
        capsys,
        "sources",
        "--project",
        str(proj),
        "set",
        dist,
        json.dumps({"path": f"../{pkg}", "desktop_only": True}),
        "--no-sync",
    )
    assert row["desktop_only"] is True and row["kind"] == "path"
    assert sources.read_project(proj)["sources"][dist] == {
        "path": f"../{pkg}",
        "editable": True,
    }
    assert row["warnings"]


def test_hot_reload_of_a_local_library(tmp_path, capsys):
    pkg = unique("hotlib")
    url, work = make_remote(tmp_path, pkg, 1)
    proj = make_project(tmp_path)
    cli(
        capsys,
        "sources",
        "--project",
        str(proj),
        "set",
        pkg,
        json.dumps({"path": f"../{pkg}"}),
        "--no-sync",
    )
    sys.path.insert(0, str(work))  # what the editable install does

    report = sources.activate(proj)
    assert (
        report["libraries"][0]["import_roots"] == [pkg]
        and report["libraries"][0]["live"]
    )
    assert importlib.import_module(pkg).VALUE == 1
    thing = importlib.import_module(f"{pkg}.parts").Thing(size=3)
    head = git("rev-parse", "HEAD", cwd=work)
    assert stamp_of(thing)["source"] == f"git {url}@{head}"

    set_value(work, pkg, 2)
    assert importlib.import_module(pkg).VALUE == 1
    purged = sources.purge()
    assert pkg in purged and f"{pkg}.parts" in purged
    assert importlib.import_module(pkg).VALUE == 2
    thing = importlib.import_module(f"{pkg}.parts").Thing(size=3)
    assert stamp_of(thing)["source"] == f"git {url}@{head} dirty"
    assert stamp_of(thing)["item"] == f"{pkg}:Thing"


def test_cloud_sync_installs_the_git_half_at_the_locked_sha(tmp_path, capsys):
    pkg = unique("cloudlib")
    dist = f"{pkg.replace('_', '-')}-dist"
    url, work = make_remote(tmp_path, pkg, 7)
    proj = make_project(tmp_path)
    cli(
        capsys,
        "sources",
        "--project",
        str(proj),
        "set",
        pkg,
        json.dumps({"path": f"../{pkg}"}),
        "--no-sync",
    )
    shutil.move(str(work), str(tmp_path / "elsewhere"))  # the cloud has no local folder

    report = cli(
        capsys, "sources", "--project", str(proj), "sync", "--runtime", "cloud"
    )
    assert report["ok"] and not report["warnings"], report
    sha = next(e["sha"] for e in sources.read_uv_lock(proj)[dist] if e["kind"] == "git")
    assert report["installed"] == [f"{dist} @ git+{url}@{sha}"]
    python = proj / ".venv" / "bin" / "python"
    out = subprocess.run(
        [str(python), "-c", f"import {pkg}; print({pkg}.VALUE)"],
        capture_output=True,
        text=True,
    )
    assert out.stdout.strip() == "7", out.stderr


def test_web_reads_the_locked_sha_and_reuses_a_prefetched_archive(
    tmp_path, monkeypatch
):
    pkg = unique("weblib")
    dist = f"{pkg.replace('_', '-')}-dist"
    sha = "b" * 40
    url = "https://github.com/acme/weblib"
    proj = make_project(tmp_path)
    (proj / "pyproject.toml").write_text(textwrap.dedent(f"""
            [project]
            name = "proj"
            version = "0.0.1"
            dependencies = ["{dist}"]

            [tool.uv.sources]
            {dist} = [
                {{ path = "../{pkg}", editable = true, marker = "{sources.LOCAL_MARKER}" }},
                {{ git = "{url}", branch = "main", marker = "{sources.WEB_MARKER}" }},
            ]
            """))
    (proj / "uv.lock").write_text(textwrap.dedent(f"""
            version = 1
            [[package]]
            name = "{dist}"
            version = "0.1.0"
            source = {{ git = "{url}?branch=main#{sha}" }}

            [[package]]
            name = "{dist}"
            version = "0.1.0"
            source = {{ editable = "../{pkg}" }}
            """))
    plan = sources.web_plan(proj)
    assert plan == [
        {
            "name": dist,
            "git": url,
            "sha": sha,
            "archive": f"https://codeload.github.com/acme/weblib/tar.gz/{sha}",
            "cache": str(Path(os.environ[sources.CACHE_ENV]) / dist / sha),
        }
    ]
    # The web host prefetched the archive (top-level folder kept).
    make_library(Path(plan[0]["cache"]) / f"weblib-{sha[:7]}", pkg, 4)
    monkeypatch.setattr(
        sources.urllib.request, "urlopen", lambda *a, **k: pytest.fail("downloaded")
    )
    report = sources.activate(proj, runtime_name="web")
    assert not report["warnings"], report
    assert importlib.import_module(pkg).VALUE == 4
    thing = importlib.import_module(f"{pkg}.parts").Thing()
    assert stamp_of(thing)["source"] == f"git {url}@{sha}"


def test_archive_url_proxy_base(monkeypatch):
    sha = "c" * 40
    assert sources._archive_url("https://github.com/acme/lib.git", sha) == (
        f"https://codeload.github.com/acme/lib/tar.gz/{sha}"
    )
    monkeypatch.setenv(
        sources.ARCHIVE_ENV, "https://hub.example/api/webcode/github-archive"
    )
    assert sources._archive_url("https://github.com/acme/lib", sha) == (
        f"https://hub.example/api/webcode/github-archive/acme/lib/{sha}"
    )
    monkeypatch.setenv(sources.ARCHIVE_ENV, "https://p/{owner}--{repo}@{sha}.tgz")
    assert (
        sources._archive_url("git@github.com:acme/lib.git", sha)
        == f"https://p/acme--lib@{sha}.tgz"
    )
    assert sources._archive_url("file:///tmp/x.git", sha) is None


def test_insert_snippet(tmp_path, capsys):
    pkg = unique("inslib")
    make_library(tmp_path / pkg, pkg, 1)
    sys.path.insert(0, str(tmp_path / pkg))
    importlib.import_module(f"{pkg}.parts")
    out = cli(
        capsys,
        "insert",
        f"{pkg}:Thing",
        json.dumps({"size": "12"}),
        "--name",
        "thing_a",
    )
    assert out == {
        "ok": True,
        "item": f"{pkg}:Thing",
        "import": f"from {pkg}.parts import Thing",
        "code": "thing_a = Thing(size=12.0)",
        "var": "thing_a",
        "dependency": None,
    }
    err = cli(capsys, "insert", "nope:Nothing")
    assert err["ok"] is False and "unknown library item" in err["error"]
