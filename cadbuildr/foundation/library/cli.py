"""``python -m cadbuildr.foundation.library``.

Every command prints one JSON document on one line; failures are
``{"ok": false, "error": "..."}`` with exit status 0.

    manifest [<import_root> ...] [--no-anchors]
        The cadbuildr.library-manifest/1 document of each library (one object
        for one root, else a list). Without roots: every installed library
        (entry point group ``cadbuildr.libraries``).
    eval [--project DIR] [--with-source]
        Read {"item", "inputs"} JSON on stdin, print {"ok": true, "dag": ...}.
    insert <item> [<inputs-json>] [--name VAR] [--project DIR] [--no-add]
           [--connect '{"own": IFACE, "target": [VAR, IFACE], "dof": {...}}'] [--assembly NAME]
        The import line and call the viewer's code sync writes; ``uv add``s the
        item's distribution when the project lacks it. ``--connect`` adds the
        ``assembly.connect(...)`` line (``{"target": null}``: ``assembly.ground``).
    connect  (JSON on stdin: {"a": side, "b": side, "dof"?, "assembly"?},
             side = {"var", "interface"?, "item", "inputs"})
        The Mate a rule gives (joint, flip, dof), its modifiers and the
        ``assembly.connect(...)`` line; ``candidates`` when a side names no interface.
    rules
        The declarative mate-rule table (cadbuildr.mate-rules/1).
    sources [--project DIR] list [--remote]
    sources [--project DIR] set <name> <json|null> [--no-sync]
        {"version": ">=0.4"} | {"git": URL, "branch"|"rev"|"tag": ...}
        | {"path": "../x", "desktop_only"?: true}  (-> path / git pair) | null (remove)
    sources [--project DIR] update <name> [--no-sync]
    sources [--project DIR] push <name> [--no-sync]
    sources [--project DIR] sync [--runtime desktop|cloud|web]
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, List, Optional


def _print(data: Any) -> None:
    """One JSON document on one line."""
    sys.stdout.write(json.dumps(data, default=str) + "\n")
    sys.stdout.flush()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m cadbuildr.foundation.library")
    sub = parser.add_subparsers(dest="command", required=True)

    m = sub.add_parser("manifest", help="print library manifests")
    m.add_argument("import_roots", nargs="*")
    m.add_argument("--no-anchors", action="store_true")

    e = sub.add_parser("eval", help="evaluate one configurable (JSON on stdin)")
    e.add_argument("--project")
    e.add_argument("--with-source", action="store_true")
    e.add_argument(
        "--interfaces", action="store_true", help="include the built interfaces"
    )

    sub.add_parser(
        "connect", help="resolve a mate between two interfaces (JSON on stdin)"
    )
    sub.add_parser("rules", help="print the mate rule table")

    ins = sub.add_parser("insert", help="import line + call for a library item")
    ins.add_argument("item")
    ins.add_argument("inputs", nargs="?", default="{}")
    ins.add_argument("--name")
    ins.add_argument("--project")
    ins.add_argument(
        "--no-add", action="store_true", help="do not uv add a missing dependency"
    )
    ins.add_argument("--connect", help="JSON: {own, target: [var, interface], dof}")
    ins.add_argument("--assembly", default="assembly")

    s = sub.add_parser("sources", help="library dependencies of a project (uv)")
    s.add_argument("--project", default=".")
    ss = s.add_subparsers(dest="action", required=True)
    lst = ss.add_parser("list")
    lst.add_argument(
        "--remote", action="store_true", help="fetch remotes (behind / drift)"
    )
    st = ss.add_parser("set")
    st.add_argument("name")
    st.add_argument("spec", help="JSON source, or null to remove")
    st.add_argument("--no-sync", action="store_true")
    for action in ("update", "push"):
        p = ss.add_parser(action)
        p.add_argument("name")
        p.add_argument("--no-sync", action="store_true")
    sy = ss.add_parser("sync")
    sy.add_argument("--runtime")
    return parser


def _manifest(args: argparse.Namespace) -> Any:
    from .registry import get_manifest
    from .sources import library_entry_points

    roots = args.import_roots or sorted(library_entry_points())
    out = []
    for root in roots:
        try:
            out.append(get_manifest(root, with_anchors=not args.no_anchors))
        except Exception as exc:
            out.append(
                {
                    "format": "cadbuildr.library-manifest/1",
                    "import_root": root,
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return out[0] if len(args.import_roots) == 1 else out


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "manifest":
            _print(_manifest(args))
        elif args.command == "eval":
            from .evaluate import evaluate

            try:
                request = json.loads(sys.stdin.read() or "{}")
            except json.JSONDecodeError as exc:
                _print({"ok": False, "error": f"invalid JSON on stdin: {exc}"})
                return 0
            if args.project and not request.get("project"):
                request["project"] = args.project
            _print(
                evaluate(
                    request,
                    with_source=args.with_source,
                    with_interfaces=args.interfaces,
                )
            )
        elif args.command == "connect":
            from .mating import connect_request

            _print(connect_request(json.loads(sys.stdin.read() or "{}")))
        elif args.command == "rules":
            from .mating import rules_document

            _print(rules_document())
        elif args.command == "insert":
            from .sources import insert

            _print(
                insert(
                    args.item,
                    json.loads(args.inputs or "{}"),
                    var=args.name,
                    project_dir=args.project,
                    ensure_dependency=not args.no_add,
                    connect=(
                        json.loads(args.connect) if args.connect is not None else None
                    ),
                    connect_given=args.connect is not None,
                    assembly=args.assembly,
                )
            )
        else:
            from . import sources

            if args.action == "list":
                _print(sources.list_sources(args.project, remote=args.remote))
            elif args.action == "set":
                spec = json.loads(args.spec)
                if spec is not None and not isinstance(spec, dict):
                    raise ValueError("set: the source must be a JSON object or null")
                _print(
                    sources.set_source(
                        args.project, args.name, spec, sync=not args.no_sync
                    )
                )
            elif args.action == "update":
                _print(
                    sources.update_source(
                        args.project, args.name, sync=not args.no_sync
                    )
                )
            elif args.action == "push":
                _print(
                    sources.push_source(args.project, args.name, sync=not args.no_sync)
                )
            elif args.action == "sync":
                _print(sources.sync_sources(args.project, args.runtime))
    except Exception as exc:  # hosts read the JSON: failures are data, not exit codes
        _print(
            {
                "ok": False,
                "error": (
                    f"{exc}"
                    if exc.__class__.__name__ == "SourceError"
                    else f"{type(exc).__name__}: {exc}"
                ),
            }
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
