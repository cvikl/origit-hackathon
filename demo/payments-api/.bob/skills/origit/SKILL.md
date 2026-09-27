---
name: origit
description: Answer provenance questions about this repository with Origit — which commits an agent wrote after reading a package, file or content hash (taint), what a commit's record says (show), and the sessions and runs behind the history (log). Use when the user asks what an agent read, which commits are affected by a dependency or advisory, or wants the Origit record of a commit.
---

Use the Origit MCP tools when they are available (`origit_taint`, `origit_show`, `origit_log`); otherwise run the CLI with execute_command: `origit taint <needle> --json`, `origit show <sha> --json`, `origit log --json`.

- Taint: name the package (`fast-pay-utils` or `fast-pay-utils@2.1.0`), file path or sha256. Report: affected commits (short sha + subject), session labels (#42), files written, approver, first read (session + time), and the roll-back commit. Say "affected means matched by provenance, not confirmed compromise".
- Show: quote the record fields (session, actor, read, wrote, added_deps, commands, tests, record_sha256) and whether the hash verified.
- Log: summarise sessions newest first: label, mode, runs, reads/writes/deps per run.
- Never modify records, notes or the taint result; Origit's deterministic code owns them. You explain and draft.
