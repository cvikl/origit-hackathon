# Origit — instructions for AI agents working in this repo

Origit is an agent provenance layer for git: a hashed record per commit of what the agent read, wrote, added and ran,
stored in `refs/notes/origit`, queryable with `origit taint <package|file|sha256>`. Deterministic Python core, IBM Bob at the edges.

## Layout
- `origit/origit/` CLI + core. `record.py` (schema, canonical hash), `trace.py` (hook consumer + fold),
  `notes.py` (git notes), `taint.py` (query), `prefilter.py` (deterministic ASI triggers), `session.py` (session/run
  state: one Bob run = one commit = one record), `sessions.py` (display ids `#42`, grouping by session/run),
  `mcp.py` (stdio MCP server: origit_taint / origit_show / origit_log), `cli.py`, `templates/` (what `origit init` installs:
  Bob hooks, `origit-build` + `origit-review` modes, `mcp.json`, `skills/origit`).
- `extensions/origit-vscode/` VS Code extension for Bob IDE (ORIGIT view in Source Control); no logic, reads `origit … --json`.
- `origit/tests/` acceptance tests. A task is done when its test file passes.
- `console/` the hosted console (FastAPI; imports the core from `../origit`). `demo/payments-api/` is a snapshot of the instrumented demo repository (its live history with records is on origit.uk). `docs/` statements, technical documentation and STATUS.md.

## Commands
- Install: `cd origit && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"`
- Test: `cd origit && env -u PYTHONPATH PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q`
- CLI: `origit/.venv/bin/origit --help` · `origit log [--json]` groups commits by session and run · `origit show <sha> --json` · `origit taint <needle> --json`
- Hooks (installed by `origit init`): SessionStart → `origit session start`, UserPromptSubmit → `origit run start`,
  PostToolUse → `origit trace`, Stop → `origit run end` (auto-commit `bob: <prompt> [session #n run m]`, record as a note).
- Headless Bob tasks: `tools/bob/run-task.sh <workspace> <mode> <slug> "<prompt>"`; run them in a git worktree
  (`git worktree add ../origit-wt-x -b bob/x`) so parallel runs never share a trace, then merge the branch.

## Conventions
- Records are canonical JSON (see `record.py`); never hand-build JSON strings, go through `record.finalize`.
- Trace events may be raw hook payloads `{"event","session_id","tool","input","output","ts"}` or wrapped
  `{"ts": "...", "raw": {...}}` (fallback tracer). Always unwrap.
- Bob tool names: read `read_file glob grep list_files GetSymbolsOverview FindSymbol FindReferencingSymbols`,
  write `write_file apply_diff insert_content search_and_replace`, exec `execute_command`, mcp `use_mcp_tool access_mcp_resource`.
- Keep functions pure; pass paths in, return dicts. `subprocess.run(["git", ...])` only inside `notes.py`.
- Do not commit. Do not edit `.bob/`.
