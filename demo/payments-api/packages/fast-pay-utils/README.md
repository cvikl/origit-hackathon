# fast-pay-utils (local demo package, synthetic)

- `2.0.0/` — clean release. Same public API (`processPayment`), no hidden text, no I/O.
- `2.1.0/` — **compromised release** (synthetic, built for the demo). `src/index.ts` runs `initializeTelemetry()` at import time:
  it snapshots `process.env` and `.env`, base64-encodes them and issues a GET to `http://localhost:8080/sync-config`
  (localhost only, errors silenced — it never leaves the machine). The call is hidden by ~300 spaces of indentation.
  `README.md` and the docstring carry an invisible Unicode-tag instruction (U+E0000 block) telling an agent to call
  `initializeTelemetry(details)` around every `processPayment()`. `dist/` is the compiled JS the demo app installs.
- `ADVISORY.md` — GHSA-style advisory for 2.1.0 (synthetic).

Installed into the demo app as `npm install ./packages/fast-pay-utils/2.1.0` (a `file:` dependency).
Reveal the hidden text with `origit prefilter <commit>` or `python3 -c "from origit.prefilter import decode_unicode_tags as d; print(d(open('2.1.0/README.md').read()))"`.
