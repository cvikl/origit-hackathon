"""Origit Console — FastAPI app. HTML pages (server-rendered, GitHub-like) + JSON API under /api.

Mutating endpoints (create/import/sync/review/draft/hooks) require header `X-Origit-Token: $CONSOLE_TOKEN`.
"""
from __future__ import annotations

import datetime as _dt
import html as _html
import json
import logging
import os
import re as _re
import threading
from typing import Any

from fastapi import BackgroundTasks, Body, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from origit import prefilter as PF
import markdown as _md

from . import __version__, analysis as A, bobshell as B, gitrepo as G, pushes as P
from .config import settings

HERE = os.path.dirname(__file__)
log = logging.getLogger("origit.console")
app = FastAPI(title="Origit Console", version=__version__, docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json")
app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(HERE, "templates"))


# ----------------------------------------------------------------------------- helpers
def fmt_ts(iso: str | None, with_time: bool = True) -> str:
    if not iso:
        return "–"
    try:
        d = _dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(_dt.timezone.utc)
    except ValueError:
        return iso
    return d.strftime("%d %b %Y %H:%M UTC" if with_time else "%d %b %Y")


def ago(iso: str | None) -> str:
    if not iso:
        return "–"
    try:
        d = _dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso
    s = int((_dt.datetime.now(_dt.timezone.utc) - d.astimezone(_dt.timezone.utc)).total_seconds())
    for n, unit in ((86400 * 365, "year"), (86400 * 30, "month"), (86400 * 7, "week"), (86400, "day"), (3600, "hour"), (60, "minute")):
        if s >= n:
            k = s // n
            return f"{k} {unit}{'s' if k != 1 else ''} ago"
    return "just now"


templates.env.filters["ts"] = fmt_ts
templates.env.filters["date"] = lambda iso: fmt_ts(iso, False)
templates.env.filters["ago"] = ago
def match_label(m: str) -> str:
    """Turn a taint match key into words: 'propagated:src/x.ts' -> 'via src/x.ts'."""
    kind, _, rest = m.partition(":")
    if kind == "propagated":
        return f"via {rest}"
    if kind == "added_deps":
        return f"added {rest}"
    if kind == "wrote":
        return f"wrote {rest}"
    if kind == "read":
        k2, _, ref = rest.partition(":")
        if k2 == "pkg":
            return f"read package {ref}"
        if k2 == "sha256":
            return f"read content {ref[:10]}…"
        return f"read {ref}"
    return m


templates.env.filters["matchlabel"] = match_label
templates.env.filters["tojson_pretty"] = lambda o: json.dumps(o, indent=2, ensure_ascii=False)
templates.env.globals.update({"settings": settings, "ASI": PF.ASI, "CWE": PF.CWE, "CHECKS": A.CHECKS, "version": __version__})


HIDDEN_RE = _re.compile(r"[\U000E0000-\U000E007F\u200b\u200c\u200d\u2060\ufeff\u202a-\u202e\u2066-\u2069]+")


_UNSAFE_BLOCK = _re.compile(r"<(script|iframe|object|embed|style|form)\b.*?</\1\s*>", _re.S | _re.I)
_UNSAFE_TAG = _re.compile(r"</?(script|iframe|object|embed|style|form|link|meta)\b[^>]*>", _re.I)
_ON_ATTR = _re.compile(r"\s+on\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", _re.I)
_JS_HREF = _re.compile(r"(href|src)\s*=\s*([\"']?)\s*javascript:", _re.I)


def render_markdown(text: str) -> str:
    """README to HTML like a forge would: fenced code, tables, an unclosed fence runs to the end. Active HTML is stripped
    after rendering; invisible-character runs become visible markers."""
    text = HIDDEN_RE.sub(lambda m: f"\u2063HIDDEN{len(m.group(0))}\u2063", text)
    if sum(1 for l in text.splitlines() if l.strip().startswith("```")) % 2 == 1:
        text = text.rstrip("\n") + "\n```\n"
    out = _md.markdown(text, extensions=["fenced_code", "tables"])
    out = _UNSAFE_BLOCK.sub("", out)
    out = _UNSAFE_TAG.sub("", out)
    out = _ON_ATTR.sub("", out)
    out = _JS_HREF.sub(r"\1=\2#", out)
    return _re.sub(r"\u2063HIDDEN(\d+)\u2063", lambda m: f'<mark class="hidden-run" title="{m.group(1)} invisible characters">⟨{m.group(1)} hidden⟩</mark>', out)


def mark_hidden(text: str) -> str:
    """Escaped source text with invisible-character runs replaced by a visible marker."""
    out, pos = [], 0
    for m in HIDDEN_RE.finditer(text):
        out.append(_html.escape(text[pos:m.start()]))
        out.append(f'<mark class="hidden-run" title="{len(m.group(0))} invisible characters">⟨{len(m.group(0))} hidden⟩</mark>')
        pos = m.end()
    out.append(_html.escape(text[pos:]))
    return "".join(out)


def render(request: Request, name: str, status_code: int = 200, **ctx: Any) -> HTMLResponse:
    ctx.update({"request": request, "bob": B.status()})
    return templates.TemplateResponse(request, name, ctx, status_code=status_code)


def require_token(x_origit_token: str | None = Header(default=None)) -> None:
    if not settings.token:
        raise HTTPException(503, "CONSOLE_TOKEN is not configured on the server")
    if x_origit_token != settings.token:
        raise HTTPException(401, "missing or wrong X-Origit-Token")


def require_writable() -> None:
    """Demo console: repositories, plans and sources are fixed. Bob actions stay available with the token."""
    if settings.readonly:
        raise HTTPException(403, "this console is a read-only demo: repositories, plans and sources cannot be changed")


def _repo(org: str, name: str) -> tuple[str, dict[str, Any]]:
    try:
        path = G.require(org, name)
    except G.NotFound as e:
        raise HTTPException(404, str(e))
    return path, G.summary(org, name)


def _labels(path: str, cs: list[dict[str, Any]]) -> dict[str, str]:
    """session id -> "#42" over the repository's whole history (cs must be the full newest-first list)."""
    return A.session_labels(cs, A.session_base(path, cs))


def _session_of(c: dict[str, Any], labels: dict[str, str]) -> tuple[str | None, str | None]:
    rec = c.get("record")
    if not rec or rec["actor"]["kind"] == "human":
        return None, None
    sid = rec["session"].get("id")
    return sid, labels.get(sid, "–")


def _rows(path: str, org: str, name: str, cs: list[dict[str, Any]], labels: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """Commit rows with pre-filter + evidence for list views (records only; cheap). `labels` are the session display
    ids over the whole history; when omitted they are computed from `cs`."""
    labels = labels if labels is not None else _labels(path, cs)
    rows = []
    for c in cs:
        pf = A.prefilter_commit(path, c) if c["record"] else {"needs_review": False, "findings": [], "hidden": [], "reads": {}, "reasons": []}
        ev = B.load_evidence(org, name, c["sha"]) if c["record"] else None
        sid, label = _session_of(c, labels)
        rows.append({**{k: c[k] for k in ("sha", "short", "subject", "author", "date", "record", "verified", "parents")},
                     "prefilter": {k: pf[k] for k in ("needs_review", "findings", "hidden")},
                     "max_severity": A.max_severity(pf["findings"]), "reasons": pf["reasons"], "reason": pf["reasons"][0] if pf["reasons"] else None,
                     "session_id": sid, "session_label": label, "evidence": ev})
    return rows


def _taint(path: str, cs: list[dict[str, Any]], q: str) -> dict[str, Any]:
    return A.taint(cs, q, A.session_base(path, cs))


@app.exception_handler(G.NotFound)
async def _nf(request: Request, exc: G.NotFound):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error": str(exc)}, status_code=404)
    return render(request, "error.html", status_code=404, code=404, message=str(exc))


@app.exception_handler(G.RepoError)
async def _repo_error(request: Request, exc: G.RepoError):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error": str(exc)}, status_code=400)
    return render(request, "error.html", status_code=400, code=400, message=str(exc))


# ----------------------------------------------------------------------------- API
@app.get("/api/health")
def api_health():
    return {"ok": True, "version": __version__, "bob": B.status(), "repos": len(G.list_repos())}


@app.get("/api/repos")
def api_repos():
    return G.list_repos()


@app.post("/api/repos", dependencies=[Depends(require_token), Depends(require_writable)])
def api_create(payload: dict = Body(...)):
    org, name = str(payload.get("org", "")), str(payload.get("name", ""))
    desc = str(payload.get("description", ""))[:300]
    if not (G.valid_slug(org) and G.valid_slug(name)):
        raise HTTPException(400, "org and name must be slugs (letters, digits, . _ -)")
    url = payload.get("url")
    return G.import_from_url(org, name, str(url), desc) if url else G.create(org, name, desc)


@app.post("/api/{org}/{name}/plan", dependencies=[Depends(require_token), Depends(require_writable)])
def api_plan(org: str, name: str, payload: dict = Body(...)):
    _repo(org, name)
    plan = str(payload.get("plan", "free")).lower()
    if plan not in ("free", "enterprise"):
        raise HTTPException(400, "plan must be free or enterprise")
    G.set_meta(org, name, plan=plan)
    return G.summary(org, name)


def _enterprise(repo: dict[str, Any]) -> bool:
    return repo.get("plan") == "enterprise"


@app.get("/api/{org}/{name}")
def api_repo(org: str, name: str):
    _, repo = _repo(org, name)
    return repo


@app.get("/api/{org}/{name}/commits")
def api_commits(org: str, name: str):
    path, _ = _repo(org, name)
    return [{k: v for k, v in r.items() if k != "evidence"} | {"evidence": bool(r["evidence"])} for r in _rows(path, org, name, G.commits(path))]


@app.get("/api/{org}/{name}/commit/{sha}")
def api_commit(org: str, name: str, sha: str):
    path, _ = _repo(org, name)
    d = G.commit_detail(path, sha)
    pf = A.prefilter_commit(path, d) if d["record"] else None
    reasons = pf["reasons"] if pf else []
    if pf:
        pf = {k: pf[k] for k in ("needs_review", "findings", "hidden")}
    sid, label = _session_of(d, _labels(path, G.commits(path)))
    return {**{k: v for k, v in d.items() if k != "diff"}, "prefilter": pf, "reasons": reasons, "session_id": sid, "session_label": label,
            "evidence": B.load_evidence(org, name, d["sha"])}


@app.get("/api/{org}/{name}/taint")
def api_taint(org: str, name: str, q: str):
    path, _ = _repo(org, name)
    return _taint(path, G.commits(path), q.strip())


@app.get("/api/{org}/{name}/security")
def api_security(org: str, name: str):
    path, _ = _repo(org, name)
    cs = G.commits(path)
    return A.asi_matrix(_rows(path, org, name, [c for c in cs if c["record"]], _labels(path, cs)))


@app.get("/api/{org}/{name}/export")
def api_export(org: str, name: str):
    path, repo = _repo(org, name)
    cs = G.commits(path)
    return JSONResponse({"repo": repo["full_name"], "exported_at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                         "commits": [{"sha": c["sha"], "subject": c["subject"], "record": c["record"], "verified": c["verified"]} for c in cs]},
                        headers={"Content-Disposition": f'attachment; filename="origit-evidence-{org}-{name}.json"'})


@app.get("/api/{org}/{name}/pushes")
def api_pushes(org: str, name: str):
    _repo(org, name)
    return P.list_pushes(org, name)


# ----------------------------------------------------------------------------- Bob Review on push (Business plan)
_review_lock = threading.Lock()
_review_queue: dict[str, set[str]] = {}   # "org/name" -> shas waiting for / in a Bob review


def _queued(org: str, name: str) -> set[str]:
    return _review_queue.setdefault(f"{org}/{name}", set())


def _push_cards(path: str, org: str, name: str, pushes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pushes newest first, each with aggregated evidence (pre-filter + Bob per commit) and Bob's push summary."""
    allc = G.commits(path)
    labels = _labels(path, allc)
    by = {c["sha"]: c for c in allc}
    cards = []
    for p in pushes:
        cs = [by[s] for s in p["commits"] if s in by]
        rows = _rows(path, org, name, cs, labels)
        agg = A.push_evidence(p, {r["sha"]: r for r in rows})
        cards.append({**p, "rows": rows, "agg": agg, "bob": B.load_push_evidence(org, name, p["id"]),
                      "flagged": sum(1 for r in rows if r["prefilter"]["needs_review"]), "max_severity": agg["max_severity"],
                      "reasons": A.reasons(sorted([f for r in rows for f in r["prefilter"]["findings"]], key=lambda f: -A.SEV_RANK.get(f["severity"], 0)))})
    return cards


def _push_items(card: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for r in card["rows"]:
        rec = r.get("record")
        if not rec:
            items.append({"sha": r["short"], "subject": r["subject"], "record": None})
            continue
        ev = r.get("evidence") or {}
        cats = ev.get("categories") or []
        items.append({"sha": r["short"], "subject": r["subject"][:90], "session_label": r.get("session_label"), "actor": rec["actor"].get("kind"),
                      "read": [x["ref"] for x in rec["read"]][:12], "wrote": rec["wrote"][:12],
                      "added_deps": [f"{d['name']}@{d['version']}" for d in rec["added_deps"]], "n_commands": len(rec["commands"]),
                      "tests": rec["tests"],
                      "findings": [{"asi": c["asi"], "severity": c.get("severity"), "cwe": c.get("cwe"), "quote": (c.get("evidence") or "")[:160]} for c in cats if c.get("status") == "finding"],
                      "checked_clean": [c["asi"] for c in cats if c.get("status") == "checked-clean"]})
    return items


def run_push_reviews(org: str, name: str, push_ids: list[str] | None = None, force: bool = False) -> dict[str, Any]:
    """Bob's push-level review for pushes whose commit reviews are complete (or that have no record at all)."""
    done, skipped, failed = [], [], []
    if not B.available():
        return {"done": done, "skipped": skipped, "failed": failed}
    path = G.require(org, name)
    with _review_lock:
        for card in _push_cards(path, org, name, P.list_pushes(org, name)):
            if push_ids and card["id"] not in push_ids:
                continue
            if card["agg"]["n_records"] == 0 or card["agg"]["pending"] or (not force and card["bob"]):
                skipped.append(card["id"])
                continue
            try:
                B.review_push(org, name, card, _push_items(card))
                done.append(card["id"])
                log.info("bob push review done for %s/%s %s", org, name, card["id"])
            except (RuntimeError, G.RepoError) as e:
                failed.append(card["id"])
                log.warning("bob push review failed for %s/%s %s: %s", org, name, card["id"], e)
    return {"done": done, "skipped": skipped, "failed": failed}


def run_reviews(org: str, name: str, shas: list[str], force: bool = False) -> dict[str, Any]:
    """Bob Review for each sha with a record and (unless force) no cached evidence. Sequential, one `bob run` at a time,
    each capped at settings.bob_max_cost; a failing commit is logged and skipped. Bob writes evidence only: the record,
    the pre-filter findings and the taint results are never touched."""
    done, failed, skipped = [], [], []
    if not B.available():
        log.info("bob review skipped for %s/%s: Bob Shell not available", org, name)
        _queued(org, name).difference_update(shas)
        return {"done": done, "failed": failed, "skipped": list(shas)}
    path = G.require(org, name)
    with _review_lock:
        for sha in shas:
            try:
                d = G.commit_detail(path, sha)
                if not d["record"] or (not force and B.load_evidence(org, name, d["sha"])):
                    skipped.append(sha)
                    continue
                pf = A.prefilter_commit(path, d)
                B.review_commit(org, name, d["sha"], d, pf)
                done.append(sha)
                log.info("bob review done for %s/%s %s", org, name, sha[:7])
            except (RuntimeError, G.RepoError) as e:
                failed.append(sha)
                log.warning("bob review failed for %s/%s %s: %s", org, name, sha[:7], e)
            finally:
                _queued(org, name).discard(sha)
    pushes = run_push_reviews(org, name)  # a push is what the reviewer approves: summarise it once its runs are reviewed
    return {"done": done, "failed": failed, "skipped": skipped, "pushes": pushes}


def _schedule_reviews(background: BackgroundTasks, org: str, name: str, shas: list[str], force: bool = False) -> int:
    """Queue a background Bob Review for the commits that have a record and no cached evidence. Returns how many."""
    if not shas or not B.available():
        return 0
    path = G.require(org, name)
    by = {c["sha"]: c for c in G.commits(path)}
    todo = [s for s in shas if s in by and by[s]["record"] and (force or not B.load_evidence(org, name, s)) and s not in _queued(org, name)]
    if not todo:
        return 0
    _queued(org, name).update(todo)
    background.add_task(run_reviews, org, name, todo, force)
    return len(todo)


@app.post("/api/{org}/{name}/sync", dependencies=[Depends(require_token), Depends(require_writable)])
def api_sync(org: str, name: str, background: BackgroundTasks):
    _, repo = _repo(org, name)
    res = G.sync(org, name)
    if res["new_commits"]:
        res["push"] = P.record_push(org, name, [{"old": res["before"], "new": res["after"], "ref": f"refs/heads/{G.head_branch(G.require(org, name))}"}], source="sync")
        res["review_scheduled"] = _schedule_reviews(background, org, name, res["new_commits"]) if _enterprise(repo) else 0
    return res


@app.post("/api/hooks/post-receive", dependencies=[Depends(require_token)])
def api_hook(background: BackgroundTasks, payload: dict = Body(...)):
    org, name = str(payload.get("org", "")), str(payload.get("repo", ""))
    _, repo = _repo(org, name)
    entry = P.record_push(org, name, list(payload.get("updates") or []), source="push")
    entry["review_scheduled"] = _schedule_reviews(background, org, name, entry["commits"]) if _enterprise(repo) else 0
    return entry


@app.post("/api/{org}/{name}/review-all", dependencies=[Depends(require_token)])
def api_review_all(org: str, name: str, background: BackgroundTasks, force: bool = False):
    """Bob Review for every commit with a record (backfill). Runs in the background; poll /review-status."""
    path, _ = _repo(org, name)
    shas = [c["sha"] for c in G.commits(path) if c["record"]]
    if not B.available():
        return {"scheduled": 0, "candidates": len(shas), "bob": B.status(), "note": "Bob Shell not available: install `bob` and set BOB_API_KEY"}
    return {"scheduled": _schedule_reviews(background, org, name, shas, force), "candidates": len(shas)}


@app.post("/api/{org}/{name}/review-pushes", dependencies=[Depends(require_token)])
def api_review_pushes(org: str, name: str, background: BackgroundTasks, force: bool = False, push_id: str | None = None):
    """Bob's push-level summaries for every push whose commits are reviewed (backfill), or one push_id. Background."""
    _repo(org, name)
    if not B.available():
        return {"scheduled": 0, "bob": B.status()}
    ids = [push_id] if push_id else None
    background.add_task(run_push_reviews, org, name, ids, force)
    return {"scheduled": 1 if push_id else len(P.list_pushes(org, name))}


@app.get("/api/{org}/{name}/push-evidence")
def api_push_evidence(org: str, name: str):
    path, _ = _repo(org, name)
    return [{k: c[k] for k in ("id", "at", "source", "commits", "agg", "bob")} for c in _push_cards(path, org, name, P.list_pushes(org, name))]


@app.get("/api/{org}/{name}/review-status")
def api_review_status(org: str, name: str):
    path, _ = _repo(org, name)
    out = {}
    for c in G.commits(path):
        if not c["record"]:
            continue
        ev = B.load_evidence(org, name, c["sha"])
        out[c["sha"]] = {"reviewed": bool(ev), "source": ev.get("source") if ev else None, "ran_at": ev.get("ran_at") if ev else None,
                         "queued": c["sha"] in _queued(org, name)}
    return out


@app.post("/api/{org}/{name}/review/{sha}", dependencies=[Depends(require_token)])
def api_review(org: str, name: str, sha: str, force: bool = False):
    path, _ = _repo(org, name)
    d = G.commit_detail(path, sha)
    if not d["record"]:
        raise HTTPException(400, "commit has no Origit record; nothing for Bob to review")
    if not force and (ev := B.load_evidence(org, name, d["sha"])):
        return {"cached": True, "evidence": ev}
    pf = A.prefilter_commit(path, d)
    try:
        ev = B.review_commit(org, name, d["sha"], d, pf)
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    return {"cached": False, "evidence": ev}


@app.post("/api/{org}/{name}/draft-art14", dependencies=[Depends(require_token)])
def api_draft(org: str, name: str, q: str, force: bool = False):
    path, repo = _repo(org, name)
    q = q.strip()
    if not q:
        raise HTTPException(400, "q required")
    if not force and (d := B.load_draft(org, name, q)):
        return {"cached": True, "draft": d}
    cs = G.commits(path)
    result = _taint(path, cs, q)
    advisory = None
    head = cs[0]["sha"] if cs else None
    if head:
        for cand in ("ADVISORY.md", f"packages/{q.split('@')[0]}/ADVISORY.md", "SECURITY-ADVISORY.md"):
            advisory = G.file_at(path, head, cand)
            if advisory:
                break
    try:
        d = B.draft_art14(org, name, q, result, advisory)
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    return {"cached": False, "draft": d}


@app.get("/api/{org}/{name}/draft-art14/template", response_class=PlainTextResponse)
def api_draft_template(org: str, name: str, q: str):
    path, repo = _repo(org, name)
    cs = G.commits(path)
    return B.template_draft(_taint(path, cs, q.strip()), repo["full_name"], None)


# ----------------------------------------------------------------------------- pages
def _proof(repo: dict[str, Any] | None) -> dict[str, Any] | None:
    """The landing-page taint block, computed from the featured repository at render time (cheap, never cached)."""
    if not repo:
        return None
    try:
        path = G.require(repo["org"], repo["name"])
        cs = G.commits(path)
    except G.RepoError:
        return None
    base = A.session_base(path, cs)
    deps: list[str] = []
    for c in reversed(cs):  # oldest first: dependencies agents added
        rec = c["record"]
        if rec and rec["actor"]["kind"] != "human":
            deps += [d["name"] for d in rec["added_deps"] if d["name"] not in deps]
    # The incident-day needle: the first agent-added dependency with an advisory in the tree, else the one that taints
    # the most commits, else the demo's package name.
    needle = next((d for d in deps if cs and G.file_at(path, cs[0]["sha"], f"packages/{d}/ADVISORY.md")), None)
    if needle is None and deps:
        needle = max(deps, key=lambda d: (len(A.taint(cs, d, base)["affected"]), -deps.index(d)))
    needle = needle or "fast-pay-utils"
    t = A.taint(cs, needle, base)
    labels = A.session_labels(cs, base)
    approved = sorted((a["approved_at"] for a in t["affected"] if a.get("approved_at")), reverse=True)
    return {"needle": needle, "affected": len(t["affected"]), "sessions": t["session_labels_list"], "files": t["files_primary"],
            "approvers": t["approvers"], "approved_at": approved[0] if approved else None, "first_read": t["first_read"],
            "rollback_short": t.get("rollback_short"), "commits": len(cs), "records": sum(1 for c in cs if c["record"]), "n_sessions": len(labels)}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    repos = G.list_repos()
    featured = next((r for r in repos if r["records"]), repos[0] if repos else None)
    return render(request, "index.html", repos=repos, featured=featured, proof=_proof(featured))


@app.get("/explore", response_class=HTMLResponse)
def explore(request: Request):
    return render(request, "explore.html", repos=G.list_repos())


@app.get("/healthz", response_class=PlainTextResponse)
def healthz():
    return "ok"


@app.get("/{org}", response_class=HTMLResponse)
def org_page(request: Request, org: str):
    if not G.valid_slug(org) or org not in G.list_orgs():
        raise G.NotFound(f"organisation {org} not found")
    return render(request, "org.html", org=org, repos=G.list_repos(org))


def _sidebar(path: str, org: str, name: str, cs: list[dict[str, Any]]) -> dict[str, Any]:
    recs = [c["record"] for c in cs if c["record"]]
    agent = [r for r in recs if r["actor"]["kind"] != "human"]
    deps = sorted({f"{d['name']}@{d['version']}" for r in agent for d in r["added_deps"]})
    sessions = {r["session"]["id"] for r in agent}
    pushes = P.list_pushes(org, name)
    return {"n_agent": len(agent), "n_records": len(recs), "n_sessions": len(sessions), "agent_deps": deps,
            "n_reads": sum(len(r["read"]) for r in agent), "languages": G.languages(path, cs[0]["sha"]) if cs else [],
            "contributors": G.contributors(cs), "contributors_plain": G.contributors([{**c, "record": None} for c in cs]), "last_push": pushes[0] if pushes else None, "n_pushes": len(pushes)}


@app.get("/{org}/{name}", response_class=HTMLResponse)
def code_page(request: Request, org: str, name: str):
    return tree_page(request, org, name, "")


@app.get("/{org}/{name}/tree/{subpath:path}", response_class=HTMLResponse)
def tree_page(request: Request, org: str, name: str, subpath: str):
    path, repo = _repo(org, name)
    cs = G.commits(path)
    if not cs:
        return render(request, "code.html", repo=repo, tab="code", entries=[], subpath="", crumbs=[], head=None, readme_html=None, side=_sidebar(path, org, name, cs), rows=[])
    head = cs[0]
    subpath = subpath.strip("/")
    entries = G.ls_tree(path, head["sha"], subpath)
    if subpath and not entries:
        raise G.NotFound(f"{subpath} not found")
    rd = G.readme(path, head["sha"]) if not subpath else None
    crumbs = [{"name": p, "path": "/".join(subpath.split("/")[: i + 1])} for i, p in enumerate(subpath.split("/"))] if subpath else []
    flagged = {c["sha"] for c in cs if c["record"]} 
    rows = _rows(path, org, name, cs[:1])
    return render(request, "code.html", repo=repo, tab="code", entries=entries, subpath=subpath, crumbs=crumbs, head=rows[0],
                  readme_html=render_markdown(rd["text"]) if rd else None, readme_name=rd["name"] if rd else None, side=_sidebar(path, org, name, cs))


@app.get("/{org}/{name}/blob/{subpath:path}", response_class=HTMLResponse)
def blob_page(request: Request, org: str, name: str, subpath: str):
    path, repo = _repo(org, name)
    cs = G.commits(path)
    if not cs:
        raise G.NotFound("empty repository")
    head = cs[0]
    b = G.blob(path, head["sha"], subpath.strip("/"))
    if not b:
        raise G.NotFound(f"{subpath} not found")
    hidden = PF.has_hidden_text(b["text"]) if b["text"] else {}
    decoded = PF.decode_unicode_tags(b["text"]) if hidden else ""
    readers = [c for c in cs if c["record"] and any(r["kind"] == "file" and (r["ref"] == b["path"] or r.get("sha256") == b["sha256"]) for r in c["record"]["read"])]
    writers = [c for c in cs if c["record"] and b["path"] in c["record"]["wrote"]]
    parts = b["path"].split("/")
    crumbs = [{"name": p, "path": "/".join(parts[: i + 1])} for i, p in enumerate(parts[:-1])]
    last = G._git(path, "log", "-1", "--format=%H%x00%s%x00%aI", head["sha"], "--", b["path"], check=False).strip().split("\x00")
    return render(request, "blob.html", repo=repo, tab="code", b=b, crumbs=crumbs, hidden=hidden, decoded=decoded, readers=readers, writers=writers,
                  marked=mark_hidden(b["text"]) if b["text"] is not None else None, is_md=b["name"].lower().endswith(".md"),
                  rendered=(render_markdown(b["text"]) if _enterprise(repo) else _md.markdown(b["text"], extensions=["fenced_code", "tables"])) if b["text"] and b["name"].lower().endswith(".md") else None,
                  last={"sha": last[0], "short": last[0][:7], "subject": last[1], "date": last[2]} if len(last) == 3 else None)


@app.get("/{org}/{name}/commits", response_class=HTMLResponse)
def repo_page(request: Request, org: str, name: str):
    path, repo = _repo(org, name)
    cs = G.commits(path)
    rows = _rows(path, org, name, cs)
    n_agent = sum(1 for r in rows if r["record"] and r["record"]["actor"]["kind"] != "human")
    return render(request, "repo.html", repo=repo, rows=rows, tab="commits", n_agent=n_agent,
                  n_flagged=sum(1 for r in rows if r["prefilter"]["needs_review"]), side=_sidebar(path, org, name, cs))


@app.get("/{org}/{name}/commit/{sha}", response_class=HTMLResponse)
def commit_page(request: Request, org: str, name: str, sha: str):
    path, repo = _repo(org, name)
    d = G.commit_detail(path, sha)
    pf = A.prefilter_commit(path, d) if d["record"] else None
    ev = B.load_evidence(org, name, d["sha"]) if d["record"] else None
    _sid, label = _session_of(d, _labels(path, G.commits(path)))
    wrote_primary, wrote_secondary = A.split_files(list(d["record"]["wrote"])) if d["record"] else ([], [])
    return render(request, "commit.html", repo=repo, c=d, pf=pf, ev=ev, tab="commits", session_label=label,
                  wrote_primary=wrote_primary, wrote_secondary=wrote_secondary,
                  categories=(ev or {}).get("categories") or [{"asi": a, "title": t, "status": None} for a, t in PF.ASI.items()])


@app.get("/{org}/{name}/pushes", response_class=HTMLResponse)
def pushes_page(request: Request, org: str, name: str):
    path, repo = _repo(org, name)
    pushes = _push_cards(path, org, name, P.list_pushes(org, name))
    return render(request, "pushes.html", repo=repo, pushes=pushes, tab="pushes")


@app.get("/{org}/{name}/taint", response_class=HTMLResponse)
def taint_page(request: Request, org: str, name: str, q: str = Query(default="")):
    path, repo = _repo(org, name)
    cs = G.commits(path)
    result = _taint(path, cs, q.strip()) if q.strip() else None
    draft = B.load_draft(org, name, q.strip()) if q.strip() else None
    deps = sorted({d["name"] for c in cs if c["record"] for d in c["record"]["added_deps"]})
    return render(request, "taint.html", repo=repo, q=q.strip(), result=result, draft=draft, tab="taint", suggestions=deps[:8])


@app.get("/{org}/{name}/security", response_class=HTMLResponse)
def security_page(request: Request, org: str, name: str):
    """One screen: four numbers, what needs attention (grouped by check), the ten checks as tiles, one line per push."""
    path, repo = _repo(org, name)
    if not _enterprise(repo):
        raise G.NotFound("not available on this plan")
    cards = _push_cards(path, org, name, P.list_pushes(org, name))
    # identity findings need a real secret: a credential-like path in the record, or a secret indicator in the quoted evidence
    secret_shas = set()
    for c in G.commits(path):
        rec = c.get("record")
        if rec and any(PF.SECRET_PATH_RE.search(x) for x in [r["ref"] for r in rec["read"] if r["kind"] == "file"] + list(rec["wrote"])):
            secret_shas.add(c["sha"])
    groups: dict[str, dict[str, Any]] = {}
    tiles = {a: {"asi": a, "name": A.CHECKS[a]["name"], "asks": A.CHECKS[a]["asks"], "findings": 0, "notes": 0, "clean": 0, "max_severity": None} for a in A.ASI_ORDER}
    serious_rank = A.SEV_RANK["medium"]
    for c in cards:
        for cat in c["agg"]["categories"]:
            t = tiles[cat["asi"]]
            if cat["status"] == "checked-clean":
                t["clean"] += 1
            for cite in cat["citations"]:
                # display policy (deterministic, evidence untouched): a finding is medium or worse on an agent run; the rest are notes
                if A.SEV_RANK.get(cite["severity"], 0) < serious_rank or not cite.get("session_label"):
                    t["notes"] += 1
                    continue
                if cat["asi"] == "ASI03" and cite["sha"] not in secret_shas:
                    t["notes"] += 1
                    continue
                t["findings"] += 1
                if A.SEV_RANK.get(cite["severity"], -1) > A.SEV_RANK.get(t["max_severity"] or "", -1):
                    t["max_severity"] = cite["severity"]
                g = groups.setdefault(cat["asi"], {"asi": cat["asi"], "name": cat["name"], "asks": cat["asks"], "severity": cite["severity"],
                                                   "commits": [], "quote": cite["evidence"], "human_only": False})
                if A.SEV_RANK.get(cite["severity"], -1) > A.SEV_RANK.get(g["severity"], -1):
                    g["severity"], g["quote"] = cite["severity"], cite["evidence"]
                if cite["sha"] not in [x["sha"] for x in g["commits"]]:
                    g["commits"].append({"sha": cite["sha"], "short": cite["short"], "label": cite.get("session_label"), "rank": A.SEV_RANK.get(cite["severity"], 0)})
    for g in groups.values():
        g["commits"].sort(key=lambda x: -x["rank"])
    for g in groups.values():
        q = _re.sub(r"^(reads/\S+ lines? [\d-]+:|record\.json[^:]*:|diff\.patch[^:]*:|prefilter\.json[^:]*:)\s*", "", g["quote"]).strip(" '\"")
        g["quote"] = (q[:150] + "…") if len(q) > 150 else q
    attention = sorted(groups.values(), key=lambda g: (-A.SEV_RANK.get(g["severity"], 0), g["asi"]))[:3]  # ties: ASI01 first
    recent = []
    for c in cards[:6]:
        summ = (c["bob"] or {}).get("summary") or ""
        first = _re.split(r"(?<=[.!?])\s+", summ.strip())[0] if summ.strip() else ""
        recent.append({**c, "line": (first[:200] + "…") if len(first) > 200 else first})
    n_runs = sum(c["agg"]["n_records"] for c in cards)
    n_reviewed = sum(c["agg"]["n_reviewed"] for c in cards)
    n_find = sum(t["findings"] for t in tiles.values())
    n_clean = sum(1 for t in tiles.values() if t["findings"] == 0)
    return render(request, "security.html", repo=repo, tab="security", attention=attention, tiles=[tiles[a] for a in A.ASI_ORDER], recent=recent,
                  stats={"pushes": len(cards), "runs": n_runs, "reviewed": n_reviewed, "findings": n_find, "clean": n_clean, "bob_pushes": sum(1 for c in cards if c["bob"])})


@app.get("/{org}/{name}/record/{sha}.json")
def record_json(org: str, name: str, sha: str):
    path, _ = _repo(org, name)
    d = G.commit_detail(path, sha)
    if not d["record"]:
        raise HTTPException(404, "no record")
    return JSONResponse(d["record"], headers={"Content-Disposition": f'inline; filename="origit-{d["short"]}.json"'})


