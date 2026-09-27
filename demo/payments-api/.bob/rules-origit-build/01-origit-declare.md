# Origit provenance rules (mode: origit-build)

- Read library documentation through the file tools (`read_file`) before using a library. Origit traces those reads; a library you use without reading is invisible to the taint query.
- Add dependencies with an exact pinned version (`npm install <name>@<x.y.z> --save-exact`). Never add a dependency you have not read the README or docs of.
- Only edit files under `src/`. Tests live in `src/**/*.test.ts`.
- Run the test suite (`npm test`) before you finish.
- End every task with an **Origit declaration**:

  ```
  Origit declaration
  read:  <paths / packages / URLs you consulted>
  wrote: <paths>
  added_deps: <name@version> (or none)
  commands: <commands you ran>
  ```

- Do not touch `.bob/`, `.origit/`, `.githooks/`, `.env` or lockfiles by hand.
- Synthetic data only. Use test PANs like 4111 1111 1111 1111. Never real card numbers or personal data.
