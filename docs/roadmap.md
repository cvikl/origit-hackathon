# Origit post-hackathon roadmap

Four items deferred from the hackathon weekend (see `docs/positioning.md` §2.5).
Listed in dependency order: the record is already landed; everything below builds on it.

---

## 1. Release check on top of the record

A policy-to-code gate, codenamed **ProofPatch**, wraps the existing Origit record in a short approval loop before the branch is merged.
Flow: a team-defined policy file (plain YAML, checked into the repo) describes what a clean commit must satisfy — no new unverified deps, no hidden-text findings, test suite green, approver in the authorised list.
Bob reads the record and the policy and writes a structured interpretation: which clauses pass, which fail, which need a human call.
That interpretation is presented to a designated reviewer who clicks **PASS**, **STOP**, or **REVIEW** in the Origit Console.
Only a PASS token (signed by the reviewer's session) unblocks the merge.
STOP aborts; REVIEW opens a findings thread that must be resolved before the loop can rerun.
Targeted tests — the subset whose `read[]` overlap with the changed files — are re-run automatically as part of the PASS condition so the gate is cheap.
No AI makes the gate decision; Bob supplies evidence and the human signs.

---

## 2. Adapters for Cursor, Codex and other coding agents

Origit's trace format is already stable (`record.py`); the missing piece is a lightweight shim that maps each agent's native event stream onto the same schema.
**Bob-native first:** the Bob IDE/Shell hook integration is the reference implementation and the one that will be demoed and supported first.
Most coding agents expose a tool-call stream or a local JSONL log that maps cleanly onto `read[]` / `commands[]`; a thin Python adapter per agent is sufficient.
Cursor exposes a plugin API; the adapter registers as a Cursor extension and forwards `onDidUseTool` events.
Codex (OpenAI Codex CLI) logs all tool calls to a local JSONL file; the adapter tails that file and posts to `origit trace`.
All three adapters must pass the same acceptance tests as the Bob adapter (session start/stop, read, write, exec events round-trip without loss) and must never replace or weaken the Bob-native integration path.
Agent-agnostic by design, Bob-native first — consistent with the positioning.

---

## 3. CI/CD gate and IDE plugin

Two distribution surfaces that widen adoption without changing the core.

**CI/CD gate:** a GitHub Actions step (and a GitLab CI equivalent) that runs `origit verify` on every push.
It fails the pipeline if any commit in the push is missing its Origit record, or if an existing record's `record_sha256` no longer matches (tampering check).
The step is a single `uses: origit-dev/origit-action@v1` line and requires no secrets beyond a repo-scoped token.

**IDE plugin:** a VS Code extension (with a JetBrains port to follow) that shows the Origit record for the commit at the current file's HEAD in a side panel — reads, writes, deps, ASI findings — without leaving the editor.
The taint command is exposed as a command-palette action: type a package name and the affected commits highlight in the Git timeline.
Both surfaces are read-only consumers of `git notes`; they add no new data path and require no console subscription to function.

---

## 4. AIVSS scoring, full CWE, and MITRE ATLAS mapping

The hackathon build uses a small fixed CWE tag set (CWE-506, CWE-829, CWE-94, CWE-200) and a CVSS-style severity label.
The roadmap item completes the vulnerability taxonomy in three steps.

**AIVSS:** adopt the AI Vulnerability Scoring System (AIVSS) schema as the canonical severity field in the Origit record and in Console findings, replacing the informal CVSS-style label.
Each finding will carry `aivss_vector` and `aivss_score` alongside the existing severity word.

**Full CWE:** extend the per-ASI CWE tag set beyond the four hackathon tags.
ASI02 Tool Misuse maps to CWE-732 (incorrect permission assignment) and CWE-862 (missing authorisation); ASI06 Context Poisoning maps to CWE-20 (improper input validation); ASI07 maps to CWE-287 (improper authentication); ASI09 maps to CWE-693 (protection mechanism failure).
The mapping table in `docs/asi-mapping.md` will be extended to cover all ten ASI categories with at least one primary CWE and one secondary CWE where applicable.

**MITRE ATLAS:** add one ATLAS tactic/technique line per ASI category to the mapping table.
ASI01 Goal Hijack → AML.T0051 (LLM Prompt Injection); ASI04 Supply Chain → AML.T0010 (ML Supply Chain Compromise); ASI05 Code Execution → AML.T0049 (Exploit Public-Facing Model); ASI03 Identity Abuse → AML.T0047 (ML-Enabled Product Abuse); the remaining six categories will be mapped once ATLAS publishes its agentic-AI extension, currently in draft.
All three enhancements land together so that the evidence pack exported by `origit export` is sufficient for a single SOC 2 / PCI artefact submission without manual annotation.
