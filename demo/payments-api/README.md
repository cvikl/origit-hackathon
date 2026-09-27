# payments-api — Origit demo repository

A small, synthetic payments API belonging to a fictional EU fintech (a CRA "manufacturer"). The team builds with
**IBM Bob IDE** and records every agent commit with **Origit** (https://github.com/cvikl/origit).

This repository is the *subject* of the Origit demo: Bob builds a payout-export feature here across three sessions,
reads the documentation of a vendored library `fast-pay-utils@2.1.0` that later turns out to be compromised, and
`origit taint fast-pay-utils` shows in seconds which commits, sessions and files are downstream of that read.

- `packages/fast-pay-utils/2.0.0` — clean release · `2.1.0` — compromised release (synthetic; see `packages/fast-pay-utils/README.md` and `ADVISORY.md`)
- `SPEC.md` — what Bob is asked to build, session by session
- `.bob/`, `.githooks/` — installed by `origit init`: lifecycle hooks (tracer), `origit-build` custom mode, git hooks

Synthetic data only. Test PAN `4111111111111111`. Nothing here performs real network I/O.

## Reproduce
```bash
pip install -e ../origit/origit          # the Origit CLI
origit init                              # already done in this repo
# work in Bob IDE, commit as usual …
origit log
origit taint fast-pay-utils
origit export > evidence.json
```
