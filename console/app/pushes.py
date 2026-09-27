"""Push log per repository: DATA_DIR/state/<org>/<name>/pushes.jsonl, appended by the post-receive hook or a sync."""
from __future__ import annotations

import json
import os
import time
from typing import Any

from . import gitrepo as G


def _file(org: str, name: str) -> str:
    return os.path.join(G.state_path(org, name), "pushes.jsonl")


def record_push(org: str, name: str, updates: list[dict[str, str]], source: str = "push") -> dict[str, Any]:
    path = G.require(org, name)
    commits: list[str] = []
    notes = False
    for u in updates:
        ref, old, new = u.get("ref", ""), u.get("old", ""), u.get("new", "")
        if ref == "refs/notes/origit":
            notes = True
            continue
        if not ref.startswith("refs/heads/") or not new or set(new) == {"0"}:
            continue
        rng = new if (not old or set(old) == {"0"}) else f"{old}..{new}"
        commits += G._git(path, "rev-list", rng, check=False).split()
    entry = {
        "id": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + (commits[0][:7] if commits else "notes"),
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": source, "refs": [u.get("ref") for u in updates], "notes_updated": notes, "commits": commits,
    }
    with open(_file(org, name), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def list_pushes(org: str, name: str) -> list[dict[str, Any]]:
    p = _file(org, name)
    if not os.path.exists(p):
        return []
    out = []
    for line in open(p, encoding="utf-8"):
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    out.reverse()
    return out
