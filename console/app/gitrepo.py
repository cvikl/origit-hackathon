"""Repository store: bare git repositories under DATA_DIR/repos/<org>/<name>.git.

The console never rewrites history. It reads commits with `git log`, records from `refs/notes/origit`
through the origit core (notes.py), and file contents at a commit with `git show <sha>:<path>`.
Reads that are not in the tree (e.g. node_modules/…) are resolved by content hash: every Origit
`read[]` entry carries the sha256 of what the agent saw, and the console looks for a blob in the
commit's tree with the same sha256 (the vendored package README in the demo repo).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import time
from typing import Any

from origit import notes as N
from origit import record as R

from .config import settings

SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
RESERVED = {"api", "static", "docs", "healthz", "explore", "login", "signin", "new", "import", "settings"}
MAX_DIFF_BYTES = 200_000


class RepoError(Exception):
    pass


class NotFound(RepoError):
    pass


def _git(path: str, *args: str, check: bool = True, input: str | None = None) -> str:
    p = subprocess.run(["git", "-C", path, *args], capture_output=True, text=True, input=input)
    if check and p.returncode != 0:
        raise RepoError(p.stderr.strip() or f"git {' '.join(args)} failed")
    return p.stdout


def valid_slug(s: str) -> bool:
    return bool(SLUG.match(s)) and s.lower() not in RESERVED and not s.endswith(".git")


def repo_path(org: str, name: str) -> str:
    if not (valid_slug(org) and valid_slug(name)):
        raise NotFound(f"invalid repository {org}/{name}")
    return os.path.join(settings.repos_dir, org, name + ".git")


def state_path(org: str, name: str) -> str:
    p = os.path.join(settings.state_dir, org, name)
    os.makedirs(p, exist_ok=True)
    return p


def exists(org: str, name: str) -> bool:
    try:
        return os.path.isdir(repo_path(org, name))
    except NotFound:
        return False


def require(org: str, name: str) -> str:
    p = repo_path(org, name)
    if not os.path.isdir(p):
        raise NotFound(f"{org}/{name} not found")
    return p


# ----------------------------------------------------------------------------- listing
def list_orgs() -> list[str]:
    if not os.path.isdir(settings.repos_dir):
        return []
    return sorted(d for d in os.listdir(settings.repos_dir) if os.path.isdir(os.path.join(settings.repos_dir, d)))


def list_repos(org: str | None = None) -> list[dict[str, Any]]:
    out = []
    for o in ([org] if org else list_orgs()):
        d = os.path.join(settings.repos_dir, o)
        if not os.path.isdir(d):
            continue
        for entry in sorted(os.listdir(d)):
            if entry.endswith(".git") and os.path.isdir(os.path.join(d, entry)):
                out.append(summary(o, entry[:-4]))
    out.sort(key=lambda r: r.get("updated_at") or "", reverse=True)
    return out


def meta(org: str, name: str) -> dict[str, Any]:
    p = os.path.join(require(org, name), "origit-console.json")
    try:
        return json.load(open(p))
    except (OSError, json.JSONDecodeError):
        return {}


def set_meta(org: str, name: str, **kw: Any) -> None:
    p = os.path.join(require(org, name), "origit-console.json")
    m = meta(org, name)
    m.update(kw)
    json.dump(m, open(p, "w"), indent=1)


def head_branch(path: str) -> str | None:
    ref = _git(path, "symbolic-ref", "-q", "HEAD", check=False).strip()
    if ref and _git(path, "rev-parse", "-q", "--verify", ref, check=False).strip():
        return ref.rsplit("/", 1)[-1]
    branches = _git(path, "for-each-ref", "--format=%(refname:short)", "refs/heads", check=False).split()
    for pref in ("main", "master"):
        if pref in branches:
            return pref
    return branches[0] if branches else None


def summary(org: str, name: str) -> dict[str, Any]:
    p = require(org, name)
    m = meta(org, name)
    branch = head_branch(p)
    n = int(_git(p, "rev-list", "--count", branch, check=False).strip() or 0) if branch else 0
    noted = len(N.noted_commits(p)) if branch else 0
    last = _git(p, "log", "-1", "--format=%aI", branch, check=False).strip() if branch else ""
    return {
        "org": org, "name": name, "full_name": f"{org}/{name}",
        "description": m.get("description", ""), "source": m.get("source"), "kind": m.get("kind", "hosted"), "plan": m.get("plan", "free"),
        "branch": branch, "commits": n, "records": noted,
        "updated_at": last or m.get("created_at"), "created_at": m.get("created_at"),
    }


# ----------------------------------------------------------------------------- create / import / sync
HOOK = """#!/bin/sh
# Origit Console post-receive hook: tell the console what was pushed (commits or refs/notes/origit).
ORG="{org}"; NAME="{name}"; URL="{url}"; TOKEN="{token}"
updates=""
while read old new ref; do
  updates="$updates{{\\"old\\":\\"$old\\",\\"new\\":\\"$new\\",\\"ref\\":\\"$ref\\"}},"
done
body="{{\\"org\\":\\"$ORG\\",\\"repo\\":\\"$NAME\\",\\"updates\\":[${{updates%,}}]}}"
curl -s -m 20 -X POST -H "Content-Type: application/json" -H "X-Origit-Token: $TOKEN" --data "$body" "$URL" >/dev/null 2>&1 || true
exit 0
"""


def install_hook(path: str, org: str, name: str) -> None:
    hooks = os.path.join(path, "hooks")
    os.makedirs(hooks, exist_ok=True)
    hp = os.path.join(hooks, "post-receive")
    with open(hp, "w") as f:
        f.write(HOOK.format(org=org, name=name, url=settings.hook_url, token=settings.token))
    os.chmod(hp, os.stat(hp).st_mode | stat.S_IEXEC)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def create(org: str, name: str, description: str = "") -> dict[str, Any]:
    p = repo_path(org, name)
    if os.path.isdir(p):
        raise RepoError(f"{org}/{name} already exists")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", p], check=True, capture_output=True)
    install_hook(p, org, name)
    json.dump({"description": description, "kind": "hosted", "created_at": _now()}, open(os.path.join(p, "origit-console.json"), "w"))
    return summary(org, name)


def import_from_url(org: str, name: str, url: str, description: str = "") -> dict[str, Any]:
    p = repo_path(org, name)
    if os.path.isdir(p):
        raise RepoError(f"{org}/{name} already exists")
    if not re.match(r"^(https?://|git@|ssh://|/)", url):
        raise RepoError("url must be https://, ssh:// or a local path")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    r = subprocess.run(["git", "clone", "-q", "--bare", url, p], capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        shutil.rmtree(p, ignore_errors=True)
        raise RepoError(r.stderr.strip()[-500:] or "clone failed")
    _git(p, "fetch", "-q", "origin", "+refs/notes/origit:refs/notes/origit", check=False)
    install_hook(p, org, name)
    json.dump({"description": description, "kind": "mirror", "source": url, "created_at": _now()}, open(os.path.join(p, "origit-console.json"), "w"))
    return summary(org, name)


def sync(org: str, name: str) -> dict[str, Any]:
    """Fetch branches + notes from the mirror source. Returns {before, after, new_commits}."""
    p = require(org, name)
    m = meta(org, name)
    branch = head_branch(p)
    before = _git(p, "rev-parse", "-q", "--verify", branch, check=False).strip() if branch else ""
    if m.get("source"):
        _git(p, "fetch", "-q", "origin", "+refs/heads/*:refs/heads/*", check=False)
        _git(p, "fetch", "-q", "origin", "+refs/notes/origit:refs/notes/origit", check=False)
    branch = head_branch(p)
    after = _git(p, "rev-parse", "-q", "--verify", branch, check=False).strip() if branch else ""
    new = []
    if after and after != before:
        rng = f"{before}..{after}" if before else after
        new = _git(p, "rev-list", rng, check=False).split()
    return {"before": before, "after": after, "new_commits": new}


# ----------------------------------------------------------------------------- reading
_LOG_FMT = "%H%x00%P%x00%an%x00%aI%x00%s%x00%b%x1e"


def commits(path: str, rev: str | None = None) -> list[dict[str, Any]]:
    """Newest-first commits with their Origit record (or None) and hash verification."""
    branch = rev or head_branch(path)
    if not branch:
        return []
    raw = _git(path, "log", f"--format={_LOG_FMT}", branch, check=False)
    noted = N.noted_commits(path)
    out = []
    for chunk in raw.split("\x1e"):
        chunk = chunk.strip("\n")
        if not chunk:
            continue
        sha, parents, author, date, subject, body = (chunk.split("\x00") + [""] * 6)[:6]
        sha = sha.strip()
        rec = N.read(path, sha) if sha in noted else None
        out.append({
            "sha": sha, "short": sha[:7], "parents": parents.split(), "author": author, "date": date,
            "subject": subject, "body": body.strip(), "record": rec,
            "verified": bool(rec and R.verify(rec)),
        })
    return out


def as_tuples(cs: list[dict[str, Any]]) -> list[tuple[str, str, dict[str, Any] | None]]:
    return [(c["sha"], c["subject"], c["record"]) for c in cs]


def resolve(path: str, ref: str) -> str:
    sha = _git(path, "rev-parse", "-q", "--verify", ref + "^{commit}", check=False).strip()
    if not sha:
        raise NotFound(f"commit {ref} not found")
    return sha


def commit_detail(path: str, sha: str) -> dict[str, Any]:
    sha = resolve(path, sha)
    cs = commits(path, sha)
    head = cs[0] if cs else None
    if not head:
        raise NotFound(sha)
    stat_txt = _git(path, "show", "--stat=100", "--format=", sha, check=False)
    names = _git(path, "diff-tree", "--no-commit-id", "-r", "--root", "--name-status", sha, check=False)
    files = [{"status": l.split("\t")[0], "path": l.split("\t")[-1]} for l in names.splitlines() if l.strip()]
    diff = _git(path, "diff-tree", "-p", "--no-commit-id", "-r", "--root", sha, check=False)
    truncated = len(diff) > MAX_DIFF_BYTES
    if truncated:
        diff = diff[:MAX_DIFF_BYTES] + "\n… (diff truncated)\n"
    head.update({"stat": stat_txt.strip(), "files": files, "diff": diff, "diff_truncated": truncated})
    return head


def file_at(path: str, sha: str, filepath: str) -> str | None:
    p = subprocess.run(["git", "-C", path, "show", f"{sha}:{filepath}"], capture_output=True)
    if p.returncode != 0:
        return None
    return p.stdout.decode("utf-8", errors="replace")


_blob_sha: dict[tuple[str, str], str] = {}


def sha256_index(path: str, sha: str) -> dict[str, str]:
    """content sha256 -> path, for every blob in the commit's tree (cached per blob id)."""
    out: dict[str, str] = {}
    for line in _git(path, "ls-tree", "-r", "-l", sha, check=False).splitlines():
        try:
            metaf, fpath = line.split("\t", 1)
            _mode, kind, blob, size = metaf.split()
        except ValueError:
            continue
        if kind != "blob" or int(size) > 2_000_000:
            continue
        key = (path, blob)
        if key not in _blob_sha:
            p = subprocess.run(["git", "-C", path, "cat-file", "blob", blob], capture_output=True)
            _blob_sha[key] = hashlib.sha256(p.stdout).hexdigest()
        out.setdefault(_blob_sha[key], fpath)
    return out


def read_texts(path: str, sha: str, rec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """For every file the agent read: {ref: {text, resolved_via, path_in_tree}} where text may be None."""
    out: dict[str, dict[str, Any]] = {}
    idx: dict[str, str] | None = None
    for r in rec.get("read", []):
        if r.get("kind") != "file":
            continue
        ref = r["ref"]
        text = file_at(path, sha, ref)
        via, where = "tree", ref
        if text is None and r.get("sha256"):
            idx = idx if idx is not None else sha256_index(path, sha)
            where = idx.get(r["sha256"], "")
            if where:
                text, via = file_at(path, sha, where), "sha256"
        if text is None:
            via, where = "unavailable", ""
        out[ref] = {"text": text, "resolved_via": via, "path_in_tree": where, "sha256": r.get("sha256")}
    return out


# ----------------------------------------------------------------------------- browsing (Code tab)
LANG_BY_EXT = {
    ".ts": "TypeScript", ".tsx": "TypeScript", ".js": "JavaScript", ".mjs": "JavaScript", ".py": "Python", ".sh": "Shell",
    ".md": "Markdown", ".json": "JSON", ".yaml": "YAML", ".yml": "YAML", ".html": "HTML", ".css": "CSS", ".toml": "TOML",
    ".go": "Go", ".rs": "Rust", ".java": "Java", ".rb": "Ruby", ".sql": "SQL",
}
LANG_COLOR = {"TypeScript": "#3178c6", "JavaScript": "#f1e05a", "Python": "#3572A5", "Shell": "#89e051", "Markdown": "#083fa1",
              "JSON": "#a0a0a0", "YAML": "#cb171e", "HTML": "#e34c26", "CSS": "#563d7c", "TOML": "#9c4221", "Go": "#00ADD8",
              "Rust": "#dea584", "Java": "#b07219", "Ruby": "#701516", "SQL": "#e38c00", "Other": "#6e7681"}


def ls_tree(path: str, rev: str, subpath: str = "") -> list[dict[str, Any]]:
    """Entries of a directory at rev, folders first, each with the last commit that touched it."""
    target = f"{rev}:{subpath}" if subpath else rev
    raw = _git(path, "ls-tree", "-l", target, check=False)
    entries = []
    for line in raw.splitlines():
        try:
            metaf, name = line.split("\t", 1)
            _mode, kind, _obj, size = metaf.split()
        except ValueError:
            continue
        full = f"{subpath}/{name}" if subpath else name
        log = _git(path, "log", "-1", "--format=%H%x00%s%x00%aI", rev, "--", full, check=False).strip().split("\x00")
        entries.append({"name": name, "path": full, "kind": "dir" if kind == "tree" else "file",
                        "size": int(size) if size.isdigit() else 0,
                        "last": {"sha": log[0], "short": log[0][:7], "subject": log[1], "date": log[2]} if len(log) == 3 else None})
    entries.sort(key=lambda e: (e["kind"] != "dir", e["name"].lower()))
    return entries


def blob(path: str, rev: str, filepath: str) -> dict[str, Any] | None:
    p = subprocess.run(["git", "-C", path, "show", f"{rev}:{filepath}"], capture_output=True)
    if p.returncode != 0:
        return None
    data = p.stdout
    binary = b"\0" in data[:8000]
    text = None if binary else data.decode("utf-8", errors="replace")
    return {"path": filepath, "name": filepath.rsplit("/", 1)[-1], "size": len(data), "binary": binary, "text": text,
            "sha256": hashlib.sha256(data).hexdigest(), "lines": (text.count("\n") + (0 if text.endswith("\n") else 1)) if text else 0}


def readme(path: str, rev: str) -> dict[str, Any] | None:
    for cand in ("README.md", "readme.md", "README", "README.txt"):
        b = blob(path, rev, cand)
        if b and not b["binary"]:
            return b
    return None


def languages(path: str, rev: str) -> list[dict[str, Any]]:
    """Bytes per language at rev from file extensions (node_modules, dist, lockfiles excluded)."""
    totals: dict[str, int] = {}
    for line in _git(path, "ls-tree", "-r", "-l", rev, check=False).splitlines():
        try:
            metaf, fpath = line.split("\t", 1)
            _mode, kind, _obj, size = metaf.split()
        except ValueError:
            continue
        if kind != "blob" or "node_modules/" in fpath or "/dist/" in fpath or fpath.endswith("package-lock.json"):
            continue
        ext = os.path.splitext(fpath)[1].lower()
        lang = LANG_BY_EXT.get(ext)
        if not lang or lang in ("Markdown", "JSON", "YAML", "TOML"):
            continue
        totals[lang] = totals.get(lang, 0) + (int(size) if size.isdigit() else 0)
    total = sum(totals.values()) or 1
    out = [{"name": k, "bytes": v, "pct": round(100 * v / total, 1), "color": LANG_COLOR.get(k, LANG_COLOR["Other"])} for k, v in totals.items()]
    out.sort(key=lambda x: -x["bytes"])
    return out


def contributors(cs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Humans by author name plus one entry per agent kind, with commit counts."""
    people: dict[str, int] = {}
    agents: dict[str, int] = {}
    for c in cs:
        rec = c.get("record")
        if rec and rec["actor"]["kind"] != "human":
            agents[rec["actor"]["kind"]] = agents.get(rec["actor"]["kind"], 0) + 1
        else:
            people[c["author"]] = people.get(c["author"], 0) + 1
    out = [{"name": n, "commits": k, "kind": "human"} for n, k in sorted(people.items(), key=lambda x: -x[1])]
    out += [{"name": "Bob IDE" if a == "bob-ide" else a, "commits": k, "kind": "agent"} for a, k in sorted(agents.items(), key=lambda x: -x[1])]
    return out
