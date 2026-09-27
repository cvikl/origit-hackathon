# Problem and Solution Statement

## The Problem

Git records what changed and who committed it. It records nothing about how an AI agent
produced a change: what it read, which packages and MCP servers it pulled in, which session
did the work, or what it was allowed to touch.

**Supply-chain attacks on AI coding agents are compounding.** H1 2026 saw 2.6× the campaign
volume of all of 2025; AI-agent tooling — MCP servers, rules files, injected README content —
was the confirmed delivery mechanism in 14 of 59 tracked campaigns (Phoenix Security, 2026).
LLMs hallucinate package names 19.7 % of the time (USENIX 2025). In a supply-chain attack
the malicious library passes all tests. The agent reads it, adds the dependency, and writes
code that calls it. The compromise is invisible until an advisory appears.

**The EU Cyber Resilience Act Article 14 went live 11 September 2026.** Any manufacturer
selling software in the EU must report a severe incident to ENISA: early warning within
24 hours of becoming aware, full notification within 72 hours, final report within the Article 14
deadlines. The clock starts the moment the team reads the advisory. Article 14(5)(b) defines a
severe incident as one capable of leading to the introduction or execution of malicious code —
a compromised library introduced by an AI agent meets that definition. No grace period.

**The question nobody can answer today:** when a library later turns out to be poisoned, which
code did an agent write after reading it? Across hundreds of agent commits, answering that
manually takes hours to days. The legal window closes before most teams have an answer.

## The Solution: Origit

Origit is an open-source agent provenance layer for git. Git stays git. Origit attaches a
hashed record to every agent commit and makes it queryable.

`origit init` installs lifecycle hooks and a git hook into any existing repo. Every agent
commit gets an Origit record — canonical JSON, SHA-256 hashed, stored via `git notes` —
capturing session id, actor (mode, model, rules hash), every file and package read (`read[]`),
files written, dependencies added, shell commands, approver, and test results. Agent commits
without a captured trace can be refused by the pre-commit hook; human commits pass through marked `actor: human`.

The hero command is `origit taint <package|file|sha256>`. It walks all records, matches
`read[]` and `added_deps[]`, and returns in seconds: affected commits, sessions, files
written, approver, first-read timestamp, and the last clean commit to roll back to.

When an advisory lands, one command produces every field the three Article 14 deadlines
require: product affected, affected files, corrective measure, and the session record sealed
at commit time — a hash proving it was captured then, not reconstructed after the fact.

The difference is not convenience. It is whether the team meets a live legal obligation or
misses it.

Origit is open-core. The CLI is free and offline. The Origit Console (paid tier) adds a web
view, OWASP Agentic Top 10 evaluation on push, and a one-click Article 14 draft. Bob-native
first, agent-agnostic by design.

Word count: 499
