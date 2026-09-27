# Origit positioning (from the team brief, 26 Sep 2026)

Internal source for statements, script and slides. Claims discipline at the bottom is binding.

## 1. The problem (locked)

Git records what changed and who committed it. It was designed for humans typing code: a commit object is tree, parent(s), author, committer, message. It records nothing about *how* an AI agent produced a change: what it **read**, which packages, tools and MCP servers it pulled in, which session did the work, what it was allowed to touch.

This matters now because:
- **Supply-chain attacks on AI coding agents are compounding.** H1 2026 already had 2.6× the campaign volume of all of 2025; AI-agent tooling (MCP servers, rules files, CLAUDE.md) was the confirmed delivery mechanism in 14 of 59 tracked campaigns (Phoenix Security tracker: https://phoenix.security/accelerating-supply-chain-attacks-npm-pypi-vsx-ai-enabled-2026/). LLMs hallucinate package names 19.7% of the time (USENIX 2025); a hallucinated `react-codeshift` landed in 237 repos. "Clinejection" (Feb 2026): one crafted GitHub issue title → prompt injection → npm token → malicious release, exploited in the wild 8 days after disclosure (https://labs.cloudsecurityalliance.org/research/csa-research-note-claude-code-github-action-prompt-injection/).
- **The EU Cyber Resilience Act, Article 14, went live on 11 September 2026.** Anyone selling software in the EU must report an actively exploited vulnerability or severe incident to ENISA: early warning within **24 hours** of becoming aware, full notification within 72 hours, final report within 14 days (vulnerability) / one month (severe incident). A compromised library introduced by an agent qualifies under Art. 14(5)(b) "introduction or execution of malicious code". The clock starts the moment the team reads the advisory. Reference: https://digital-strategy.ec.europa.eu/en/policies/cyber-resilience-act
- **Financial regulators carved agents out of model-risk rules** (US Fed SR 26-2 / OCC 2026-13 / FDIC FIL-15-2026, 17 Apr 2026) and pushed them to enterprise risk management. Examiners are asking anyway. MAS Singapore put agentic AI inside binding guidelines on 5 Aug 2026.

**The question nobody can answer today:** when a library / MCP server / README later turns out to be poisoned — *which code did an agent write after reading it?*

---

## 2. The solution (locked): Origit

**Origit is an open-source agent provenance layer for git.** Tagline: *versioning for agents*. Git stays git. Origit attaches a hashed record to every agent commit and makes it queryable.

### 2.1 Origit core — open source, free, offline
- `origit init` in any existing repo. Installs Bob IDE hooks, an `origit-build` custom mode, and git hooks. Adopts existing history (older commits simply have no record).
- Every agent commit gets an **Origit record**, canonical JSON, SHA-256 hashed, stored in the repo via `git notes` (namespace `refs/notes/origit`). Fields:
  - `session` — Bob task/session id, start/end timestamps
  - `actor` — `bob-ide`, model (if exposed), mode slug, hash of rules/mode files in effect
  - `read[]` — every file/package/doc/MCP output the agent consumed: `{kind: file|pkg|url|mcp, ref, sha256}`
  - `wrote[]` — files written
  - `added_deps[]` — dependencies added (name, version, registry, lockfile hash)
  - `commands[]` — shell commands executed
  - `author`, `approver` (human), `approved_at`
  - `tests` — `{run, passed, failed}` from the existing test suite (plain git hook, no AI)
  - `record_sha256`
- **Rule: a commit without a record does not exist.** `pre-commit` hook refuses agent commits that have no captured trace. (Human commits are allowed through, marked `actor: human`.)
- `origit log` — commits with their records.
- `origit show <commit>` — full record.
- **`origit taint <package|file|sha256>`** — the hero command. Walks all records, matches `read[]` and `added_deps[]`, returns: affected commits, sessions, files written, approvers, first-read timestamp, and the last clean commit to roll back to. Must return in seconds on the demo repo.
- `origit export` — JSON evidence pack (all records for a range).

### 2.2 Origit Console — paid tier, powered by IBM Bob
A GitHub-like web view of the repo with agent context visible. Bob lives here.
- **Push view:** list of pushes → commits → record. Session id, reads, writes, deps, approver.
- **ASI evaluation on push:** Bob evaluates what the push *exposed* against the **OWASP Top 10 for Agentic Applications** (https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/) and attaches **cited evidence** per category — not a score, a finding an auditor can read. All ten categories are shown; most are `N/A` for a code commit. Demo focus: **ASI01 Goal Hijack** (instructions hidden in what the agent read), **ASI04 Supply Chain** (compromised dependency), **ASI05 Unexpected Code Execution** (agent-generated call to a malicious function). ASI03 only if secrets/env are touched. Each finding carries a CVSS-style severity label (informational/low/medium/high/critical) and a small fixed CWE tag set (CWE-506 embedded malicious code, CWE-829 untrusted functionality, CWE-94 code injection, CWE-200 info exposure).
- **Deterministic pre-filter first, Bob second.** Pre-filter (no coins): new dependency present? external read present? command executed? agent config files (`.bob/`, `CLAUDE.md`, rules, skills) changed? **Unicode tag characters `[\u{E0000}-\u{E007F}]` or other invisible/bidi characters in any read input?** Only if the pre-filter fires does Bob read the trace and write evidence. Most commits cost zero coins.
- **Taint view:** search box; enter a package/file → affected commits light up red, clean ones stay green; side panel shows affected files, sessions, approver, roll-back commit. Button: "Draft Article 14 notification" → Bob drafts the ENISA early-warning text from the record.
- **ASI tracker:** per repo, which categories were checked on which pushes, open findings, trend.

### 2.4 Positioning
- "Agent provenance layer for git" (Bernard's wording). Never "we rewrote git".
- Pedigree (May winner) signed the *output*. Origit records the *input*. One step earlier. Say this once.
- Bob-native first, agent-agnostic by design (Cursor, Codex and other coding agents could emit the same trace via adapters). Do not say "works with any agent" in a way that makes Bob sound replaceable.
- Open-core, like git → GitHub. Free layer wins adoption; console is what a bank buys to prove what its agents did.
- Language: OWASP ASI codes, CRA 24h clock, CVSS severity, evidence pack for SOC 2 / PCI. Fintech judges speak this.

### 2.5 Explicit non-goals for this weekend (roadmap slide only)
- Policy-to-code release gate (ProofPatch: policy → Bob's interpretation → human approval → targeted tests → PASS/STOP/REVIEW). Mention as "release check on top of the record". Not built.
- Full mandate enforcement / sandboxing of the agent.
- CI/CD integration, IDE plugin, multi-agent adapters.
- AIVSS, full CWE, MITRE ATLAS beyond one mapping line in the report.
- Anything that needs a database bigger than SQLite or JSON files.

---

## 7. Claims discipline (from the team's own rules)

Say: "agent provenance layer for git", "records what the agent read", "answers the CRA 24-hour question in seconds", "cited evidence per ASI category", "deterministic pre-filter, Bob explains intent", "open-core", "Bob-native first, agent-agnostic by design".

Never say: "proves the code is safe", "nothing was missed", "replaces git", "works with any agent" (unqualified), "PCI-DSS compliant", "Bob guarantees…". Bob evaluates; deterministic code records and queries. Bob's ASI output is evidence, never a gate decision.

---

## How IBM Bob is actually used (as built, 26 Sep)
1. **Actor** — Bob IDE builds the demo feature in the `origit-build` custom mode (edit restricted to `src/**`), across three sessions; a fourth clean session for contrast.
2. **Tracer** — Bob IDE / Bob Shell lifecycle hooks (`SessionStart`, `PreToolUse`, `PostToolUse`, `Stop`) pipe every tool call to `origit trace`; verified live: payload carries session id, tool name, path, command.
3. **Reviewer** — Bob (Bob Shell, ask mode) reads the record, the decoded hidden text, the diff and the OWASP Agentic Top 10 rulebook and writes cited evidence per ASI01–ASI10 in the hosted Origit Console (origit.uk). Only when the deterministic pre-filter fires.
4. **Drafter** — Bob drafts the CRA Article 14 early warning from the taint result, and drafted the incident summary (`docs/incident-2026-09-26.md`).
5. **Builder** — Bob IDE task screenshots in `bob_sessions/` from every team member; headless run stats as JSON next to them.
