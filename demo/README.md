# demo

- `payments-api/` — a snapshot of the fictional fintech's repository that IBM Bob IDE works in with Origit installed
  (`origit init`): the app, `.bob/` (hooks, modes, MCP server, skill), `.githooks/`, `.origit/config.json` (session base #42)
  and the vendored `fast-pay-utils` 2.0.0 (clean) and 2.1.0 (compromised, synthetic) under `packages/`. The snapshot is the
  tree at commit `970e7f9`; the full history with the Origit records (`refs/notes/origit`) is browsable live at
  https://origit.uk/acme-payments/payments-api.
- `evidence/` — committed output of the CLI on that history so nobody needs the live repo: `export.json` (`origit export`,
  every record), `log.json`/`log.txt` (`origit log`, sessions #42–#49), `taint-fast-pay-utils.json` and `taint.txt`
  (`origit taint`), `prefilter-<sha>.json` (deterministic ASI findings per commit).

The demo story is in [`../docs/demo-script.md`](../docs/demo-script.md).
