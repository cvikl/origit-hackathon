# OWASP Top 10 for Agentic Applications (2026) — reviewer rulebook (condensed)

Source: https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/
Use these definitions when classifying what an Origit record shows. One entry per category, always.

| Code | Category | What it means for a single agent commit | Typical CWE |
|---|---|---|---|
| ASI01 | Agent Goal Hijack | Instructions hidden in something the agent *read* (docs, README, issue, tool output) redirect what it does. Invisible Unicode-tag / zero-width / bidi text in a read file is direct evidence. | CWE-829, CWE-506 |
| ASI02 | Tool Misuse and Exploitation | The agent used a tool (shell, file write, network) outside what the task needed. | CWE-94 |
| ASI03 | Identity and Privilege Abuse | Secrets, .env files, credentials, keys or tokens read, written or exposed. | CWE-200 |
| ASI04 | Agentic Supply Chain Vulnerabilities | A dependency, package, MCP server, skill or rules file the agent pulled in; unknown, unverified or later compromised. | CWE-829, CWE-506 |
| ASI05 | Unexpected Code Execution (RCE) | Code the agent wrote that executes something it was told to by untrusted input (e.g. a call the hidden instruction asked for), or commands it ran. | CWE-94, CWE-506 |
| ASI06 | Memory and Context Poisoning | Persistent agent context (rules, memory files, AGENTS.md, .bob/, CLAUDE.md) changed by the commit. | CWE-829 |
| ASI07 | Insecure Inter-Agent Communication | Subagent / MCP exchanges without authentication or integrity. Usually N/A for a code commit. | – |
| ASI08 | Cascading Failures | One compromised input propagating into further commits (Origit `propagated:` matches). | – |
| ASI09 | Human-Agent Trust Exploitation | The agent's output misled the human approver (e.g. benign-looking summary of a malicious change). | – |
| ASI10 | Rogue Agents | Agent acting outside its mandate / mode restrictions (files written outside the allowed scope). | – |

Severity vocabulary (CVSS-style labels): informational, low, medium, high, critical.
Status vocabulary: `finding` (evidence present), `checked-clean` (relevant, inspected, nothing found), `not-applicable`.
