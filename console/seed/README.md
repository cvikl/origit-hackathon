# seed/

Cached IBM Bob output that ships with the console image so the demo shows evidence even when Bob Shell is not
installed or `BOB_API_KEY` is unset.

- `evidence/<org>/<name>/<sha>.json`: the reviewer's cited OWASP ASI01–ASI10 evidence for one commit, exactly as
  `bobshell.review_commit` stored it (`source` becomes `seed` when served from here).
- `drafts/<org>/<name>/<needle>.json`: the Article 14(4)(a) early-warning draft for one taint query.

This is real Bob output, produced by `bob run` on the real records, and then copied out of a running server's state
directory with `scripts/seed-from-state.sh [state-dir]`. Nothing here is hand-written. Files under `DATA_DIR/state`
take precedence over the seed, and `POST /api/<org>/<name>/review/<sha>?force=true` or `review-all?force=true`
regenerates them.

Rule: Bob evaluates and drafts; deterministic code records and queries. Bob never edits a record or a taint result.
