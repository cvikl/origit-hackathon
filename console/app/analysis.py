"""Deterministic analysis over Origit records (zero Bobcoins): pre-filter per commit, taint queries, ASI matrix.

Everything here is a pure function of the repository contents. Bob's evidence (bobshell.py) is layered on top.
"""
from __future__ import annotations

from typing import Any

import json
import re

from origit import prefilter as PF
from origit import sessions as S
from origit import taint as X

from . import gitrepo as G

ASI_ORDER = list(PF.ASI.keys())
SEV_RANK = {s: i for i, s in enumerate(PF.SEVERITIES)}

# Pre-filter findings in words, derived from the rule that produced them (evidence prefix, see origit.prefilter.RULES).
_REASONS = (
    ("agent added dependency", "new dependency"),
    ("agent read external content", "external read"),
    ("command matches a code-execution pattern", "code-execution command"),
    ("agent configuration changed by human", "config changed by human"),
    ("agent configuration changed by the agent", "agent changed its own config"),
    ("hidden characters in agent configuration", "hidden text in config"),
    ("instruction in agent configuration", "instruction injected in config"),
    ("invisible characters", "hidden text in input"),
    ("secret or credential file", "secret file touched"),
)

# Paths that are "also touched" rather than primary work: vendored packages, tests, test config, lockfiles, manifests.
_SECONDARY_RE = re.compile(
    r"(^|/)node_modules/|(^|/)__tests__/|\.(test|spec)\.[^/]+$|(^|/)jest\.config\.[^/]+$|(^|/)package\.json$"
    r"|(^|/)(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|poetry\.lock|uv\.lock|Pipfile\.lock|Cargo\.lock|Gemfile\.lock|go\.sum|composer\.lock)$"
)


def reason_for(f: dict[str, Any]) -> str:
    ev = str(f.get("evidence") or "")
    if ev.startswith("agent added dependency") and "without reading" in ev:
        return "dependency not read"
    for prefix, words in _REASONS:
        if ev.startswith(prefix):
            return words
    return str(f.get("title") or f.get("asi") or "flagged").lower()


def reasons(findings: list[dict[str, Any]]) -> list[str]:
    """Unique reasons in severity order (findings are sorted highest severity first)."""
    out: list[str] = []
    for f in findings:
        r = f.get("reason") or reason_for(f)
        if r not in out:
            out.append(r)
    return out


def is_secondary(path: str) -> bool:
    return bool(_SECONDARY_RE.search(path))


def split_files(paths: list[str]) -> tuple[list[str], list[str]]:
    """(primary, secondary): primary is everything that is not a vendored/test/lockfile/manifest path."""
    primary = [p for p in paths if not is_secondary(p)]
    secondary = [p for p in paths if is_secondary(p)]
    return primary, secondary


# ----------------------------------------------------------------------------- sessions
def session_base(path: str, cs: list[dict[str, Any]]) -> int:
    """`.origit/config.json` {"session_base": 42} at HEAD, else 1."""
    if not cs:
        return 1
    text = G.file_at(path, cs[0]["sha"], ".origit/config.json")
    if not text:
        return 1
    try:
        return int(json.loads(text).get("session_base", 1))
    except (ValueError, TypeError, AttributeError):
        return 1


def session_labels(cs: list[dict[str, Any]], base: int = 1) -> dict[str, str]:
    """session id -> short display label ("#42") over the whole history, deterministic."""
    return {sid: S.label(n) for sid, n in S.number_sessions(G.as_tuples(cs), base).items()}


def prefilter_commit(path: str, c: dict[str, Any]) -> dict[str, Any]:
    """Run the origit pre-filter on one commit. Returns {needs_review, findings, hidden, reads}."""
    rec = c.get("record")
    if not rec:
        return {"needs_review": False, "findings": [], "hidden": [], "reads": {}}
    changed = [f["path"] for f in G.commit_detail(path, c["sha"])["files"]] if "files" not in c else [f["path"] for f in c["files"]]
    reads = G.read_texts(path, c["sha"], rec)
    texts = {ref: r["text"] for ref, r in reads.items() if r["text"] is not None}
    # content of changed agent-config files after the commit, for the insider / self-modification rule
    changed_texts = {}
    for p in changed:
        if PF.AGENT_CONFIG_RE.search(p):
            t = G.file_at(path, c["sha"], p)
            if t is not None and len(t) < 200_000:
                changed_texts[p] = t
    findings = PF.run(rec, changed, texts, changed_texts)
    hidden = []
    for ref, text in texts.items():
        counts = PF.has_hidden_text(text)
        if counts:
            hidden.append({"ref": ref, "counts": counts, "decoded": PF.decode_unicode_tags(text)[:600],
                           "path_in_tree": reads[ref]["path_in_tree"], "resolved_via": reads[ref]["resolved_via"]})
    findings.sort(key=lambda f: -SEV_RANK.get(f["severity"], 0))
    for f in findings:
        f["reason"] = reason_for(f)
    return {"needs_review": PF.needs_review(findings), "findings": findings, "hidden": hidden, "reads": reads, "reasons": reasons(findings)}


def max_severity(findings: list[dict[str, Any]]) -> str | None:
    if not findings:
        return None
    return max((f["severity"] for f in findings), key=lambda s: SEV_RANK.get(s, 0))


def taint(cs: list[dict[str, Any]], needle: str, base: int = 1) -> dict[str, Any]:
    """origit.taint.query plus what the console shows: short shas, dates, session display labels and the
    primary / secondary split of the files written."""
    out = X.query(G.as_tuples(cs), needle)
    by = {c["sha"]: c for c in cs}
    labels = session_labels(cs, base)
    for a in out["affected"]:
        a["short"] = a["sha"][:7]
        a["date"] = by[a["sha"]]["date"]
        a["session_label"] = labels.get(a["session"], "–")
    def _num(sid: str) -> int:
        l = labels.get(sid, "")
        return int(l[1:]) if l[1:].isdigit() else 10**9
    out["session_labels"] = {sid: labels.get(sid, "–") for sid in sorted(out["sessions"], key=_num)}  # in #number order
    out["session_labels_list"] = list(out["session_labels"].values())
    out["files_primary"], out["files_secondary"] = split_files(out["files_written"])
    if out["first_read"]:
        out["first_read"]["label"] = labels.get(out["first_read"]["session"], "–")
    for c in out["clean"]:
        c["short"] = c["sha"][:7]
        c["date"] = by[c["sha"]]["date"]
        c["actor"] = (by[c["sha"]]["record"] or {}).get("actor", {}).get("kind")
    if out["rollback_commit"]:
        out["rollback_short"] = out["rollback_commit"][:7]
        out["rollback_subject"] = by[out["rollback_commit"]]["subject"]
    return out


def asi_matrix(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """rows: [{sha, short, subject, date, prefilter: {...}, evidence: {...}|None}] newest first.
    Returns per-category totals and the per-commit status grid used by the Security tab."""
    cats = {a: {"asi": a, "title": PF.ASI[a], "findings": 0, "checked": 0, "na": 0, "open": []} for a in ASI_ORDER}
    grid = []
    for r in rows:
        cells = {}
        ev = (r.get("evidence") or {}).get("categories") or []
        evmap = {e["asi"]: e for e in ev}
        pf = {f["asi"] for f in r.get("prefilter", {}).get("findings", [])}
        for a in ASI_ORDER:
            e = evmap.get(a)
            if e:
                st = e.get("status", "not-applicable")
                if st == "finding":
                    cats[a]["findings"] += 1
                    cats[a]["open"].append({"sha": r["sha"], "short": r["short"], "severity": e.get("severity"), "subject": r["subject"]})
                elif st == "checked-clean":
                    cats[a]["checked"] += 1
                else:
                    cats[a]["na"] += 1
                cells[a] = {"status": st, "severity": e.get("severity"), "source": "bob"}
            elif a in pf:
                cells[a] = {"status": "triggered", "severity": max_severity([f for f in r["prefilter"]["findings"] if f["asi"] == a]), "source": "prefilter"}
            else:
                cells[a] = {"status": "none", "severity": None, "source": None}
        grid.append({**{k: r[k] for k in ("sha", "short", "subject", "date")}, "cells": cells, "needs_review": r.get("prefilter", {}).get("needs_review"),
                     "session_id": r.get("session_id"), "session_label": r.get("session_label"), "reasons": r.get("reasons") or []})
    return {"categories": [cats[a] for a in ASI_ORDER], "grid": grid}


# ----------------------------------------------------------------------------- per-push evidence (Business plan)
# Plain-language description of every check, for people who do not read OWASP codes. Bob's per-run evidence is
# aggregated per push: a push is what a reviewer approves, a run/commit is what Bob produced.
CHECKS = {
    "ASI01": {"name": "Hidden or injected instructions", "asks": "Did anything the agent read try to steer it?",
              "looks_at": "the exact text of every file, README and tool output the agent read, invisible Unicode characters decoded"},
    "ASI02": {"name": "Tool use beyond the task", "asks": "Did the agent use shell, file or network tools the task did not need?",
              "looks_at": "the commands and writes in the record versus the task"},
    "ASI03": {"name": "Secrets and credentials", "asks": "Were keys, .env files or card data read, written or exposed?",
              "looks_at": "paths read and written, the diff"},
    "ASI04": {"name": "Dependencies and supply chain", "asks": "What did the agent pull in, and was it verified?",
              "looks_at": "added dependencies, lockfile hash, whether the docs were read"},
    "ASI05": {"name": "Code and commands the agent executed or generated", "asks": "Did untrusted input turn into executed or generated code?",
              "looks_at": "commands run, generated calls versus what hidden text asked for"},
    "ASI06": {"name": "Changes to the agent's own instructions", "asks": "Did the push change rules, modes, hooks or memory the agent obeys?",
              "looks_at": "changes under .bob/, AGENTS.md, CLAUDE.md, skills"},
    "ASI07": {"name": "Agent-to-agent traffic", "asks": "Did subagents or MCP servers exchange data without integrity?",
              "looks_at": "MCP and subagent reads in the record"},
    "ASI08": {"name": "Spread to later work", "asks": "Does a tainted input propagate into later commits?",
              "looks_at": "files written by affected runs that later runs read"},
    "ASI09": {"name": "Misleading the approver", "asks": "Could the agent's summary have hidden what the change really does?",
              "looks_at": "the agent's own summary versus the diff"},
    "ASI10": {"name": "Acting outside its mandate", "asks": "Did the agent write where its mode forbids?",
              "looks_at": "files written versus the mode's allowed paths"},
}


def push_evidence(push: dict[str, Any], rows_by_sha: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Aggregate Bob's per-commit evidence (and the pre-filter) over the commits of one push.

    Returns {n_commits, n_records, n_reviewed, pending, max_severity, categories: [{asi, name, asks, status, severity,
    citations: [{sha, short, subject, session_label, severity, cwe, evidence}]}], findings: [...top citations...],
    clean: [asi...], na: [asi...]}. status: finding | checked-clean | not-applicable | pending (records not yet reviewed).
    """
    rows = [rows_by_sha[s] for s in push.get("commits", []) if s in rows_by_sha]
    recs = [r for r in rows if r.get("record")]
    reviewed = [r for r in recs if r.get("evidence")]
    cats = []
    all_cites = []
    for a in ASI_ORDER:
        cites, clean, na = [], 0, 0
        for r in reviewed:
            for e in (r["evidence"].get("categories") or []):
                if e.get("asi") != a:
                    continue
                if e.get("status") == "finding":
                    c = {"sha": r["sha"], "short": r["short"], "subject": r["subject"], "session_label": r.get("session_label"),
                         "severity": e.get("severity") or "low", "cwe": e.get("cwe"), "evidence": (e.get("evidence") or "")[:400],
                         "rationale": (e.get("rationale") or "")[:300], "asi": a, "name": CHECKS[a]["name"]}
                    cites.append(c)
                    all_cites.append(c)
                elif e.get("status") == "checked-clean":
                    clean += 1
                else:
                    na += 1
        # the pre-filter also counts as a finding source when Bob has not run yet
        pf_hits = [f for r in recs if not r.get("evidence") for f in r.get("prefilter", {}).get("findings", []) if f.get("asi") == a]
        for r in recs:
            if r.get("evidence"):
                continue
            for f in r.get("prefilter", {}).get("findings", []):
                if f.get("asi") == a:
                    c = {"sha": r["sha"], "short": r["short"], "subject": r["subject"], "session_label": r.get("session_label"),
                         "severity": f.get("severity") or "low", "cwe": f.get("cwe"), "evidence": f.get("evidence", "")[:400],
                         "rationale": "pre-filter (deterministic); Bob has not reviewed this commit yet", "asi": a, "name": CHECKS[a]["name"]}
                    cites.append(c)
                    all_cites.append(c)
        cites.sort(key=lambda c: -SEV_RANK.get(c["severity"], 0))
        if cites:
            status = "finding"
        elif len(reviewed) < len(recs):
            status = "pending" if clean == 0 else "checked-clean"
        elif clean:
            status = "checked-clean"
        else:
            status = "not-applicable"
        cats.append({"asi": a, **CHECKS[a], "status": status, "severity": cites[0]["severity"] if cites else None, "citations": cites,
                     "n_clean": clean, "n_na": na})
    all_cites.sort(key=lambda c: -SEV_RANK.get(c["severity"], 0))
    return {
        "n_commits": len(push.get("commits", [])), "n_records": len(recs), "n_reviewed": len(reviewed), "pending": len(recs) - len(reviewed),
        "max_severity": all_cites[0]["severity"] if all_cites else None,
        "categories": cats, "findings": all_cites[:6], "n_findings": len(all_cites),
        "clean": [c["asi"] for c in cats if c["status"] == "checked-clean"], "na": [c["asi"] for c in cats if c["status"] == "not-applicable"],
        "sessions": sorted({r.get("session_label") for r in recs if r.get("session_label")}, key=lambda x: (len(x), x)),
    }
