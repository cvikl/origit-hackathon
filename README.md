# Origit — versioning for agents

> **IBM Bob 2.0 Hackathon submission (lablab.ai, 25–27 September 2026).**
> Live console: **https://origit.uk** · Demo repository on the console: [acme-payments/payments-api](https://origit.uk/acme-payments/payments-api) · Video: [`video/`](video/) · Slides and statements: [`docs/`](docs/) · Bob IDE task evidence: [`bob_sessions/`](bob_sessions/) · Technical documentation: [`docs/TECHNICAL.md`](docs/TECHNICAL.md) ([PDF](docs/TECHNICAL.pdf))
>
> This repository holds everything: the open-source core (`origit/`), the hosted console (`console/`), the Bob IDE extension (`extensions/`), a snapshot of the instrumented demo repository with the exported records (`demo/`), the docs and the Bob session evidence. The core alone is also published at https://github.com/cvikl/origit.

**Origit is an open-source agent provenance layer for git.** Git records *what* changed and *who* committed it.
Origit attaches a hashed record to every agent commit saying *what the agent read, wrote, added and ran* — and makes it queryable.

> Git tells you what changed. Origit tells you what the agent read before it changed it.

Built for the [IBM Bob 2.0 Hackathon](https://lablab.ai/ai-hackathons/ibm-bob-2-hackathon) (lablab.ai, Sep 2026).
**IBM Bob IDE is the actor, the tracer, the reviewer and the drafter** — see [Origit for Bob IDE](#origit-for-bob-ide).

## Why now

- Supply-chain attacks on AI coding agents are compounding: H1 2026 had 2.6× the campaign volume of all of 2025, and AI-agent tooling (MCP servers, rules files) was the delivery mechanism in 14 of 59 tracked campaigns ([Phoenix Security](https://phoenix.security/accelerating-supply-chain-attacks-npm-pypi-vsx-ai-enabled-2026/)).
- **EU Cyber Resilience Act, Article 14** is live since 11 Sep 2026: early warning to ENISA within **24 hours** of becoming aware of an actively exploited vulnerability or severe incident, full notification within 72 h ([CRA](https://digital-strategy.ec.europa.eu/en/policies/cyber-resilience-act)). A compromised library introduced by an agent qualifies under Art. 14(5)(b).
- The question nobody can answer today: *when a library / MCP server / README turns out to be poisoned — which code did an agent write after reading it?*

## What it does

| Command | What it answers |
|---|---|
| `origit init` | Installs Bob IDE hooks, the `origit-build` and `origit-review` modes, the Origit MCP server, the `/origit` skill and git hooks into an existing repo |
| `origit trace` | Hook consumer: appends every Bob tool call to `.origit/trace.jsonl` |
| `origit record` | Folds the trace into a canonical, SHA-256-hashed record stored in `refs/notes/origit` |
| `origit session start / status` | Opens a new recording session (assigned display number) / shows current session state |
| `origit run start / end` | Marks the start / end of one Bob run (one commit) within the session |
| `origit log --json` | Sessions newest first, with runs, read/write/dep counts and commit shas |
| `origit log` / `origit show <commit>` | Commits with their records / the full record |
| **`origit taint <package\|file\|sha256>`** | Affected commits, sessions, files written, approvers, first-read time, last clean commit to roll back to |
| `origit mcp` | Start the MCP server (stdio, JSON-RPC 2.0) so Bob can answer provenance questions in chat |
| `origit export` | JSON evidence pack for a commit range |

**Rule: a commit without a record does not exist.** Every commit gets a record; agent commits without a captured trace can be refused by the pre-commit hook (`ORIGIT_REQUIRE_TRACE=1`). Human commits pass through, marked `actor: human`. Since Sunday the Stop hook commits each Bob run itself: **one Bob run = one commit = one record**.

## The record

Canonical JSON (sorted keys, no whitespace, UTF-8), SHA-256 hashed, stored as a git note. See [`origit/origit/record.py`](origit/origit/record.py) for the schema.

```
session · actor · read[] {kind: file|pkg|url|mcp, ref, sha256} · wrote[] · added_deps[] · commands[]
author · approver · approved_at · tests {run, passed, failed} · record_sha256
```

## Origit Console (powered by IBM Bob)

A GitHub-like view of the repo with agent context visible: push → commits → record, session labels (`#42`), hash verified on every view. **Free plan:** records, file provenance, taint, evidence pack. **Business plan (Bob Review):** on every push a **deterministic pre-filter** runs (new dependency? external read? command executed? agent config changed? invisible Unicode-tag characters in anything the agent read?) and IBM Bob then reads the record, the decoded hidden text, the diff and the [OWASP Top 10 for Agentic Applications](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/) rulebook and writes **cited evidence per ASI01–ASI10 category** with CVSS-style severity and CWE for every new commit. Taint view lights affected commits red; one button asks Bob to draft the CRA Article 14 early warning from the record; a Security tab tracks coverage per push. Rule: **Bob evaluates and drafts; deterministic code records and queries. Bob never edits a record or a taint result.** Live: https://origit.uk

## Origit for Bob IDE

`origit init` wires up four integration points in the `.bob/` directory of any instrumented repo: lifecycle hooks, two custom modes, an MCP server, and a skill. Each is described below.

### Session manager

One Bob session contains many runs. **One run = one commit = one record.**

The four Bob IDE lifecycle hooks (installed into [`.bob/settings.json`](origit/origit/templates/bob/settings.json)) drive the session state machine:

| Hook | Runs | Effect |
|---|---|---|
| `SessionStart` | `origit session start` | Creates `.origit/session.json`, assigns display number |
| `UserPromptSubmit` | `origit run start` | Commits any human edits since last run as `actor: human`; increments run counter; saves prompt for the commit subject |
| `PostToolUse` | `origit trace` | Appends every tool call to `.origit/trace.jsonl` — the source of `read[]` |
| `Stop` | `origit run end` | Folds the trace, runs tests, auto-commits, attaches the SHA-256 record as a git note |

The generated commit subject follows the format:

```
bob: <first line of the prompt> [session #42 run 1]
```

Human edits made between runs are committed with `actor: human` so the record stays accurate. When a run produces no file changes the record is stored under `.origit/runs/<session>-<run>.json` rather than attached to a commit note.

Tests are run by a plain hook at `Stop` time and recorded in the `tests` field of the record. **Failed tests are recorded, never gated** — the record is evidence, not a gate.

### Modes

[`custom_modes.yaml`](origit/origit/templates/bob/custom_modes.yaml) installs two modes:

**🧾 `origit-build`** — the writing mode. File edits are limited to `src/**`. Before touching a library the agent reads its documentation via `read_file` so the read is traced. Each task ends with an "Origit declaration" listing files read, files written, dependencies added and commands run. The agent does not run `git commit`; `origit run end` commits each run automatically.

**🛡 `origit-review`** — a read-only reviewer. Given a commit and its Origit record it evaluates the diff and all read inputs against the OWASP Top 10 for Agentic Applications and outputs cited evidence per category ASI01–ASI10. It never edits files and never runs state-changing git commands. Invoke in chat with:

```
Review commit HEAD with Origit
```

The output is a JSON object with one entry per OWASP category (`finding | checked-clean | not-applicable`), severity, CWE, and verbatim evidence quoted from the record or diff.

### MCP server

[`.bob/mcp.json`](origit/origit/templates/bob/mcp.json) registers the Origit MCP server so Bob can answer provenance questions in chat without leaving the IDE:

```json
{
  "mcpServers": {
    "origit": {
      "command": "origit",
      "args": ["mcp"],
      "alwaysAllow": ["origit_taint", "origit_show", "origit_log"]
    }
  }
}
```

`origit mcp` runs over stdio, JSON-RPC 2.0, calling the deterministic core directly (no model, no network). It exposes three read-only tools:

| Tool | Input | What it returns |
|---|---|---|
| `origit_taint` | `needle` (package name, spec, file path, or sha256) | Affected commits, session labels, files written, approvers, first-read time, rollback commit |
| `origit_show` | `commit` (default: `HEAD`) | sha, subject, verified flag, full record |
| `origit_log` | `limit` (default: 20) | Sessions newest first, summarised runs (read/write/dep counts, approver) |

Example question answered in chat: *"Which commits read fast-pay-utils and what did they write?"*

### /origit skill

[`.bob/skills/origit/SKILL.md`](origit/origit/templates/bob/skills/origit/SKILL.md) is activated automatically whenever the user asks a provenance question. It instructs Bob to:

- prefer the MCP tools (`origit_taint`, `origit_show`, `origit_log`) when available, fall back to `execute_command` otherwise;
- report taint results including affected commits, session labels, files written, approver, first-read time, and rollback commit;
- always add the qualifier *"affected means matched by provenance, not confirmed compromise"*;
- never modify records, notes or taint results.

### VS Code extension

`extensions/origit-vscode/` adds an **ORIGIT** view to the Source Control sidebar. It contains no logic of its own — all data comes from `origit log/show/taint --json`.

The view shows: sessions → runs/commits → reads, writes, deps, approver, record hash. Each entry carries a severity dot derived from the deterministic pre-filter (same signal the console uses to decide whether to call the reviewer).

Two additional surfaces:

- **Origit: Taint…** command (Command Palette) — enter a package name, file path or sha256; affected commits are highlighted in the tree.
- **Status bar item** — `Origit: session #48 run 1 · recording` visible whenever a session is active.

Install from the `.vsix` via **Extensions → ··· → Install from VSIX**.

### How IBM Bob is used

| Role | Actor |
|---|---|
| **Actor** | Bob IDE in `origit-build` mode — records what the agent read, wrote, added and ran |
| **Tracer** | Lifecycle hooks (`SessionStart → UserPromptSubmit → PostToolUse → Stop`) wired by `origit init` |
| **Reviewer** | `origit-review` mode (IDE) and Bob Shell in the console — writes cited OWASP ASI01–ASI10 evidence JSON per commit |
| **Drafter** | Drafts the CRA Article 14 early-warning notification from the record |
| **Builder** | Bob wrote the MCP server, the VS Code extension and parts of the docs; session summaries are in [`bob_sessions/`](bob_sessions/) |

## Technical documentation

Architecture, record schema, session manager, taint and pre-filter algorithms, Bob IDE integration, console internals and API, extension, deployment: [`docs/TECHNICAL.md`](docs/TECHNICAL.md).

## Repository layout

```
video/       demo video link (submitted through the form)
origit/      CLI + core (Python 3.11+, click only)
console/     Origit Console: FastAPI web console with agent provenance, Bob Review on push, Article 14 draft (live at https://origit.uk)
extensions/  origit-vscode: "Origit for Bob IDE" (ORIGIT view in Source Control, Origit: Taint…, status bar), packaged .vsix
demo/        payments-api (snapshot of the fintech's repo Bob works in, with its .bob/ config) + evidence pack (records, taint, log)
docs/        statements, ASI mapping, CRA note, demo script, roadmap, STATUS.md
bob_sessions/  PNG screenshots of Bob IDE task session summaries (all team members)
slides/      final deck
```

## Quick start

```bash
cd origit && pip install -e .
cd /path/to/your/repo && origit init --session-base 1   # Bob hooks, modes, MCP server, skill, git hooks
# work in Bob IDE: every run is committed and recorded when Bob stops
origit log            # sessions → runs → records
origit taint fast-pay-utils
# demo evidence without the live repo: demo/evidence/taint.txt · live history: https://origit.uk/acme-payments/payments-api
```

## Positioning

Agent provenance layer for git. Pedigree (May 2026 winner) signed the *output*; Origit records the *input* — one step earlier. Bob-native first, agent-agnostic by design. Open-core: the free layer wins adoption; the console is what a bank buys to prove what its agents did.

## References

- Hackathon: https://lablab.ai/ai-hackathons/ibm-bob-2-hackathon · guide: https://lablab-ibm-bob-2-hackathon-guide.s3.us.cloud-object-storage.appdomain.cloud/index.html
- Bob IDE docs: https://bob.ibm.com/docs/ide · hooks: https://bob.ibm.com/docs/ide/configuration/lifecycle-hooks · custom modes: https://bob.ibm.com/docs/ide/configuration/custom-modes · rules: https://bob.ibm.com/docs/ide/configuration/rules · subagents: https://bob.ibm.com/docs/ide/features/subagents
- OWASP Top 10 for Agentic Applications: https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/
- EU CRA: https://digital-strategy.ec.europa.eu/en/policies/cyber-resilience-act
- Supply-chain stats: https://phoenix.security/accelerating-supply-chain-attacks-npm-pypi-vsx-ai-enabled-2026/ · Clinejection: https://labs.cloudsecurityalliance.org/research/csa-research-note-claude-code-github-action-prompt-injection/ · hallucinated packages: https://www.augmentcode.com/guides/sbom-for-agent-driven-pipelines
- CVSS: https://www.first.org/cvss/calculator/3.0 · CWE: https://cwe.mitre.org/data/index.html · MITRE ATLAS: https://atlas.mitre.org/matrices/ATLAS-matrix · Unicode tag smuggling: https://embracethered.com/blog/ascii-smuggler.html
- Benchmark (May winner): https://lablab.ai/ai-hackathons/ibm-bob-hackathon/ctrlcats/pedigree

## License

MIT — see [LICENSE](LICENSE).
