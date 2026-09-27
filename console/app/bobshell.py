"""IBM Bob as reviewer and drafter, via Bob Shell (`bob run`) from the console backend.

Reviewer: given an Origit record, the deterministic pre-filter findings, what the agent read (with any
Unicode-tag text decoded) and the commit diff, Bob writes cited evidence per OWASP ASI01–ASI10 category.
Drafter: given a taint result, Bob drafts the CRA Article 14(4)(a) early warning.

Rules: Bob is only called when the pre-filter fired (or a human presses the button). Bob's output is
evidence, never a gate decision. Every run is cached under DATA_DIR/state/<org>/<name>/ so the console
still shows the evidence when Bob is unavailable. If `bob` is not installed or BOB_API_KEY is unset, the
console says so and serves cached / seeded evidence only.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from typing import Any

from origit import prefilter as PF

from . import gitrepo as G
from .config import settings

MAX_DIFF = 25_000
MAX_READ = 20_000
_SKIP_DIFF_RE = re.compile(r"(^|/)(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|poetry\.lock|Cargo\.lock|go\.sum)$|(^|/)(node_modules|dist|build|vendor)/|\.min\.(js|css)$|\.(png|jpg|gif|ico|woff2?|pdf)$")


def trim_diff(diff: str) -> str:
    """Drop lockfiles, vendored/compiled and binary files from the patch Bob reads (they burn turns, never evidence),
    note what was dropped, then cap the size."""
    parts = re.split(r"(?m)^(?=diff --git )", diff)
    kept, dropped = [], []
    for part in parts:
        if not part.strip():
            continue
        m = re.match(r"diff --git a/(\S+) b/", part)
        path = m.group(1) if m else ""
        if path and _SKIP_DIFF_RE.search(path):
            dropped.append(f"{path} ({part.count(chr(10))} lines)")
        else:
            kept.append(part)
    out = "".join(kept)
    if dropped:
        out = "# Origit: omitted from this patch (lockfiles / vendored / compiled files, still listed in record.wrote): " + ", ".join(dropped) + "\n" + out
    if len(out) > MAX_DIFF:
        out = out[:MAX_DIFF] + "\n# Origit: patch truncated here\n"
    return out


def status() -> dict[str, Any]:
    return {"installed": shutil.which("bob") is not None, "api_key": bool(settings.bob_api_key),
            "max_cost": settings.bob_max_cost, "max_turns": settings.bob_max_turns}


def available() -> bool:
    s = status()
    return s["installed"] and s["api_key"]


def _prompt(name: str) -> str:
    return open(os.path.join(settings.prompts_dir, name), encoding="utf-8").read()


def _balanced(text: str, start: int) -> str | None:
    """The JSON object starting at text[start] == '{' with balanced braces (string-aware), or None if unterminated."""
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _extract_json(text: str) -> Any:
    """Bob's answer -> dict. Prefers the last ```json fence; falls back to the last balanced object that has "categories"."""
    candidates: list[str] = []
    for m in re.finditer(r"```(?:json)?\s*(\{)", text):
        obj = _balanced(text, m.start(1))
        if obj:
            candidates.append(obj)
    for m in re.finditer(r"\{", text):
        if '"categories"' in text[m.start():m.start() + 400]:
            obj = _balanced(text, m.start())
            if obj:
                candidates.append(obj)
    i, j = text.find("{"), text.rfind("}")
    if i >= 0 and j > i:
        candidates.insert(0, text[i:j + 1])
    for cand in reversed(candidates):
        for attempt in (cand, _repair(cand)):
            try:
                return json.loads(attempt)
            except json.JSONDecodeError:
                continue
    return json.loads("")


def _repair(cand: str) -> str:
    r"""Models sometimes emit shell-style escapes (\$, \() inside JSON strings; double the backslash so json.loads accepts them."""
    return re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", cand)


def run(prompt: str, files: dict[str, str], attach: list[str], max_cost: float | None = None, max_turns: int | None = None) -> dict[str, Any]:
    """One `bob run --format json` in a throwaway workspace containing `files`. Returns the parsed result envelope
    plus {'last_message', 'stats', 'cmd', 'elapsed_s'}. Raises RuntimeError if bob is unavailable or fails."""
    if not available():
        raise RuntimeError("Bob Shell not available: install `bob` and set BOB_API_KEY")
    ws = tempfile.mkdtemp(prefix="origit-bob-")
    for rel, content in files.items():
        p = os.path.join(ws, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
    full = prompt.rstrip() + "\n\nFiles: " + " ".join(f"@{a}" for a in attach)
    cmd = ["bob", "run", "--format", "json", "--mode", "ask", "--max-cost", str(max_cost or settings.bob_max_cost),
           "--max-turns", str(max_turns or settings.bob_max_turns), "--workspace", ws, "--disable-mcp", "--disable-subagents",
           "--trust", "--accept-license", full]
    env = {**os.environ, "BOB_API_KEY": settings.bob_api_key, "HOME": os.environ.get("HOME", "/root")}
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=settings.bob_timeout, env=env, cwd=ws)
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"bob run timed out after {settings.bob_timeout}s") from e
    finally:
        shutil.rmtree(ws, ignore_errors=True)
    out = p.stdout.strip()
    env_obj: dict[str, Any] = {}
    for line in reversed(out.splitlines()):  # bob prints one JSON object per line; the result envelope is the last one
        line = line.strip()
        if line.startswith("{"):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") == "result" or "last_message" in obj:
                env_obj = obj
                break
    if not env_obj and "{" in out:
        try:
            env_obj = json.loads(out[out.index("{"):])
        except json.JSONDecodeError:
            env_obj = {}
    if p.returncode != 0 and not env_obj:
        raise RuntimeError((p.stderr or p.stdout).strip()[-800:] or f"bob exited {p.returncode}")
    return {"last_message": env_obj.get("last_message") or out, "stats": env_obj.get("stats", {}),
            "status": env_obj.get("status"), "elapsed_s": round(time.time() - t0, 1),
            "cmd": " ".join(cmd[:-1]) + " '<prompt>'"}


# ----------------------------------------------------------------------------- evidence cache
def _evidence_file(org: str, name: str, sha: str) -> str:
    d = os.path.join(G.state_path(org, name), "evidence")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{sha}.json")


_REDACT = [n.strip() for n in os.environ.get("REDACT_NAMES", "").split(",") if n.strip()]


def redact(obj: Any) -> Any:
    """Display rule: personal names never appear in Bob's quoted evidence. Stored files are left as Bob wrote them."""
    if isinstance(obj, str):
        for n in _REDACT:
            obj = re.sub(re.escape(n), "a contributor", obj, flags=re.I)
        return obj
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    if isinstance(obj, dict):
        return {k: redact(v) for k, v in obj.items()}
    return obj


def load_evidence(org: str, name: str, sha: str) -> dict[str, Any] | None:
    for p in (_evidence_file(org, name, sha), os.path.join(settings.seed_dir, "evidence", org, name, f"{sha}.json")):
        if os.path.exists(p):
            try:
                ev = json.load(open(p, encoding="utf-8"))
                ev.setdefault("source", "seed" if "seed" in p else "bob")
                return redact(ev)
            except (OSError, json.JSONDecodeError):
                continue
    return None


def save_evidence(org: str, name: str, sha: str, ev: dict[str, Any]) -> None:
    json.dump(ev, open(_evidence_file(org, name, sha), "w", encoding="utf-8"), indent=1, ensure_ascii=False)


def normalise_categories(cats: Any) -> list[dict[str, Any]]:
    """Whatever Bob returned -> exactly one entry per ASI01..ASI10, fixed vocabulary."""
    by = {}
    if isinstance(cats, dict):
        cats = [{"asi": k, **(v if isinstance(v, dict) else {"status": str(v)})} for k, v in cats.items()]
    for c in cats or []:
        if isinstance(c, dict) and str(c.get("asi", "")).upper() in PF.ASI:
            by[str(c["asi"]).upper()] = c
    out = []
    for a in PF.ASI:
        c = by.get(a, {})
        st = str(c.get("status", "not-applicable")).lower().replace("_", "-").replace(" ", "-")
        if st not in ("finding", "checked-clean", "not-applicable"):
            st = "finding" if st.startswith("find") else ("checked-clean" if "clean" in st or "check" in st else "not-applicable")
        sev = str(c.get("severity", "") or "").lower()
        if sev not in PF.SEVERITIES:
            sev = None if st != "finding" else "low"
        cwe = c.get("cwe")
        out.append({"asi": a, "title": PF.ASI[a], "status": st, "severity": sev if st == "finding" else None,
                    "cwe": cwe if isinstance(cwe, str) and cwe.upper().startswith("CWE-") else None,
                    "evidence": str(c.get("evidence") or "").strip()[:2000], "rationale": str(c.get("rationale") or "").strip()[:2000]})
    return out


def review_commit(org: str, name: str, sha: str, detail: dict[str, Any], pf: dict[str, Any]) -> dict[str, Any]:
    """Ask Bob for ASI evidence on one commit and cache it."""
    rec = detail["record"]
    files = {
        "record.json": json.dumps(rec, indent=1, ensure_ascii=False),
        "prefilter.json": json.dumps({"needs_review": pf["needs_review"], "findings": pf["findings"], "hidden_text": pf["hidden"]}, indent=1, ensure_ascii=False),
        "diff.patch": trim_diff(detail["diff"]),
        "ASI-RULEBOOK.md": _prompt("asi-rulebook.md"),
    }
    attach = ["record.json", "prefilter.json", "diff.patch", "ASI-RULEBOOK.md"]
    for ref, r in pf["reads"].items():
        if r["text"] is None:
            continue
        safe = "reads/" + re.sub(r"[^A-Za-z0-9._-]+", "_", ref)[:120] + ".txt"
        text = r["text"][:MAX_READ]
        decoded = PF.decode_unicode_tags(text)
        if decoded:
            text = f"### DECODED UNICODE-TAG TEXT HIDDEN IN THIS FILE (invisible to a human reader):\n{decoded}\n### END DECODED\n\n" + text
        files[safe] = text
        attach.append(safe)
    prompt = _prompt("asi-reviewer.md")
    res = run(prompt, files, attach)
    try:
        parsed = _extract_json(res["last_message"])
    except (ValueError, json.JSONDecodeError):
        parsed = {}
    ev = {
        "sha": sha, "ran_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "source": "bob",
        "reviewer": "IBM Bob (Bob Shell `bob run`, ask mode)", "stats": res["stats"], "elapsed_s": res["elapsed_s"],
        "summary": str(parsed.get("summary", "") if isinstance(parsed, dict) else "")[:1500],
        "categories": normalise_categories(parsed.get("categories") if isinstance(parsed, dict) else None),
        "raw": res["last_message"][:20000], "parsed_ok": bool(parsed),
    }
    save_evidence(org, name, sha, ev)
    return ev


# ----------------------------------------------------------------------------- Article 14 draft
def _draft_file(org: str, name: str, needle: str) -> str:
    d = os.path.join(G.state_path(org, name), "drafts")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, re.sub(r"[^A-Za-z0-9._@-]+", "_", needle) + ".json")


def load_draft(org: str, name: str, needle: str) -> dict[str, Any] | None:
    for p in (_draft_file(org, name, needle), os.path.join(settings.seed_dir, "drafts", org, name, os.path.basename(_draft_file(org, name, needle)))):
        if os.path.exists(p):
            try:
                return json.load(open(p, encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
    return None


def template_draft(taint: dict[str, Any], repo_full: str, advisory: str | None) -> str:
    """Deterministic fallback so the page is never empty. Clearly labelled: not Bob's text."""
    fr = taint.get("first_read") or {}
    lines = [
        "# CRA Article 14(4)(a) — EARLY WARNING (template, generated without Bob)",
        "", f"Product: {repo_full}", f"Awareness: <time the advisory was read>", f"Trigger: {taint['needle']}",
        f"Affected commits: {', '.join(c['short'] for c in taint['affected']) or 'none'}",
        f"Agent sessions: {', '.join(taint['sessions']) or 'none'}",
        f"Files written after the read: {', '.join(taint['files_written']) or 'none'}",
        f"Approver(s): {', '.join(taint['approvers']) or 'none'}",
        f"First read of the component: session {fr.get('session')} at {fr.get('at')}",
        f"Indication of malicious code: {'see advisory' if advisory else 'to be confirmed'}",
        f"Corrective measure available: roll back to commit {taint.get('rollback_short') or '-'} and remove the dependency.",
        "Member states affected: <placeholder>",
        "", "This is a fixed template filled from the Origit taint result. Press “Draft with Bob” for the drafted notification.",
    ]
    return "\n".join(lines)


def draft_art14(org: str, name: str, needle: str, taint: dict[str, Any], advisory: str | None) -> dict[str, Any]:
    files = {"taint.json": json.dumps(taint, indent=1, ensure_ascii=False)}
    attach = ["taint.json"]
    if advisory:
        files["ADVISORY.md"] = advisory[:MAX_READ]
        attach.append("ADVISORY.md")
    res = run(_prompt("art14-early-warning.md").replace("{{repo}}", f"{org}/{name}").replace("{{needle}}", needle), files, attach)
    d = {"needle": needle, "ran_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "source": "bob",
         "drafter": "IBM Bob (Bob Shell `bob run`)", "stats": res["stats"], "elapsed_s": res["elapsed_s"], "text": res["last_message"]}
    json.dump(d, open(_draft_file(org, name, needle), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    return d


# ----------------------------------------------------------------------------- per-push review (Business plan)
def _push_file(org: str, name: str, push_id: str) -> str:
    d = os.path.join(G.state_path(org, name), "push-evidence")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, re.sub(r"[^A-Za-z0-9._-]+", "_", push_id) + ".json")


def load_push_evidence(org: str, name: str, push_id: str) -> dict[str, Any] | None:
    fn = os.path.basename(_push_file(org, name, push_id))
    for p in (_push_file(org, name, push_id), os.path.join(settings.seed_dir, "push-evidence", org, name, fn)):
        if os.path.exists(p):
            try:
                ev = json.load(open(p, encoding="utf-8"))
                ev.setdefault("source", "seed" if "seed" in p else "bob")
                return redact(ev)
            except (OSError, json.JSONDecodeError):
                continue
    return None


def review_push(org: str, name: str, push: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
    """Ask Bob for the push-level summary and verdicts from the per-commit evidence; cache it by push id."""
    payload = {"push": {k: push.get(k) for k in ("id", "at", "source", "commits")}, "commits": items}
    files = {"push.json": json.dumps(payload, indent=1, ensure_ascii=False)[:MAX_DIFF]}
    res = run(_prompt("push-reviewer.md"), files, ["push.json"], max_cost=min(settings.bob_max_cost, 0.3), max_turns=max(settings.bob_max_turns, 10))
    try:
        parsed = _extract_json(res["last_message"])
    except (ValueError, json.JSONDecodeError):
        parsed = {}
    verdicts = normalise_categories(parsed.get("verdicts") if isinstance(parsed, dict) else None)
    by = {v["asi"]: v for v in verdicts}
    for v in (parsed.get("verdicts") or []) if isinstance(parsed, dict) else []:
        if isinstance(v, dict) and str(v.get("asi", "")).upper() in by:
            by[str(v["asi"]).upper()]["note"] = str(v.get("note") or "")[:300]
    ev = {"push_id": push["id"], "ran_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "source": "bob",
          "reviewer": "IBM Bob (Bob Shell `bob run`, ask mode)", "stats": res["stats"], "elapsed_s": res["elapsed_s"],
          "summary": str(parsed.get("summary", "") if isinstance(parsed, dict) else "")[:1200],
          "first_action": str(parsed.get("first_action", "") if isinstance(parsed, dict) else "")[:400],
          "verdicts": verdicts, "raw": res["last_message"][:12000], "parsed_ok": bool(parsed)}
    json.dump(ev, open(_push_file(org, name, push["id"]), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    return ev
