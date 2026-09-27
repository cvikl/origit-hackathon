# Origit Console — origit.uk

Hosted web view of git repositories **with agent provenance**. The hosted tier of [Origit](https://github.com/cvikl/origit), the open-source agent provenance layer for git. Built for the IBM Bob 2.0 Hackathon (Sep 2026).

> Git tells you what changed. Origit tells you what the agent read before it changed it.

**Rule:** Bob evaluates and drafts; deterministic code records and queries. Bob never edits a record or a taint result.

## Plans

- **Free**: a plain hosted repository with the Origit record on every commit, file provenance and taint queries.
- **Business plan** (internal plan value `enterprise`, set with `POST /api/<org>/<name>/plan {"plan":"enterprise"}`): everything above plus the deterministic pre-filter, **Bob Review on push**, the OWASP ASI evidence and security tracker, and Article 14 drafts.

### Bob Review on push

On the Business plan every push (post-receive hook or `sync`) is recorded, pre-filtered and then handed to IBM Bob in the background: for each new commit that has an Origit record and no cached evidence the console runs `bob run` (ask mode, capped at `BOB_MAX_COST` Bobcoins per commit, one commit at a time) and stores the cited ASI01–ASI10 evidence next to the commit. The push returns immediately; `GET /api/<org>/<name>/review-status` tells which commits are reviewed, queued or pre-filter-only, and the Security tab shows the coverage per push. `POST /api/<org>/<name>/review-all` backfills every commit with a record. Without `bob` or `BOB_API_KEY` the console keeps working on the pre-filter and cached/seeded evidence and says "IBM Bob not configured" in the header.

## What it shows

- **Commits** with their Origit record: session (short display id `#42`, full id on hover), actor (Bob IDE / human), what was read, written, added, run; approver; tests; SHA-256 of the record, re-verified on view.
- **Pushes**: every push is pre-filtered on arrival (deterministic, zero Bobcoins). Flags say why in words: new dependency, dependency not read, external read, commands run, agent config changed, hidden text in input, secret file touched.
- **Bob evidence**: when the pre-filter fires, IBM Bob (Bob Shell `bob run`, ask mode) reads the record, the exact text the agent read (hidden text decoded), the diff and the OWASP Agentic Top 10 rulebook, and writes **cited evidence per ASI01–ASI10 category**. Evidence, never a gate decision.
- **Taint**: package / file / sha256 → affected commits (red), clean commits (green), sessions, files written (primary files first; tests, vendored packages, lockfiles and manifests collapsed under "also touched"), approver, first-read time, roll-back commit.
- **Article 14**: one button drafts the EU CRA Art. 14(4)(a) early warning from the taint result (Bob), or a plain template without Bob.
- **Security tracker**: which ASI categories were checked on which commits, open findings.
- **Evidence pack**: JSON export of all records.

Reads that are not in the tree (e.g. `node_modules/<pkg>/README.md`) are resolved by content hash: the record carries the sha256 of what the agent saw, and the console finds a committed blob with the same hash.

## Run locally

This directory is the console's source inside the Origit repository; it imports the core from the sibling `../origit` package. Deploys run from a checkout where the core is the `vendor/origit` submodule the Dockerfile copies.

```bash
uv venv .venv && uv pip install -e ".[dev]"     # needs git; the core comes from ../origit
bash scripts/dev.sh                             # imports ../origit-demo-payments-api into ./data, serves :8787
```

## Hosting a repository

The public instance at https://origit.uk is a **read-only demo** of one Business-plan workspace (`CONSOLE_READONLY=1`, `DEMO_ACCOUNT=acme-payments`): repositories, plans and sources cannot be changed there. On your own instance:

Hosted repos are bare git repositories under `/srv/origit/repos/<org>/<name>.git` with a post-receive hook that tells the console what arrived. Records travel as git notes, so push them with the branch:

```bash
git remote add origit git@<your-console-host>:/srv/origit/repos/<org>/<name>.git
git push origit main refs/notes/origit
```

Or mirror an existing public repository: `POST /api/repos {"org","name","url"}` then `POST /api/<org>/<name>/sync`.

## API

`GET /api/health` · `GET /api/repos` · `GET /api/<org>/<name>` · `GET /api/<org>/<name>/commits|commit/<sha>|taint?q=|security|pushes|export|review-status` (commit, taint and security responses carry `session_label` fields, taint also `files_primary` / `files_secondary`).
Mutations (header `X-Origit-Token`): `POST /api/repos` · `POST /api/<org>/<name>/plan` · `POST /api/<org>/<name>/sync` · `POST /api/<org>/<name>/review/<sha>` · `POST /api/<org>/<name>/review-all?force=false` (background, returns `{"scheduled": n}`) · `POST /api/<org>/<name>/draft-art14?q=` · `POST /api/hooks/post-receive`. Interactive docs at `/api/docs`.

## Deploy

`deploy/publish.sh` rsyncs to the server, builds the image (Python 3.12 + git + Node 24 + Bob Shell best-effort), starts the container on the shared Caddy network and installs the Caddy drop-in for `origit.uk`. Configuration in `.env` (never committed): `BOB_API_KEY` (Bob Shell, Inference scope), `CONSOLE_TOKEN`.

## Layout

```
app/          FastAPI app: gitrepo.py (bare repos, records, content-hash resolution), analysis.py (pre-filter, taint, ASI matrix),
              bobshell.py (Bob reviewer + drafter, cached), pushes.py, main.py, templates/, static/
prompts/      asi-reviewer.md, asi-rulebook.md, art14-early-warning.md
seed/         evidence/<org>/<name>/<sha>.json and drafts/ shipped with the image (real Bob output cached for the demo; refresh with scripts/seed-from-state.sh)
scripts/      dev.sh, push-demo.sh, seed-from-state.sh
deploy/       Dockerfile, docker-compose.yml, origit-uk.caddy, publish.sh
```

MIT. Synthetic demo data only; no client, personal or confidential data.
