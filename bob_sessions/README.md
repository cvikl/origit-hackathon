# bob_sessions

PNG screenshots of **Bob IDE task session consumption summaries**, one per task, from **every team member**.

How: Bob IDE → Tasks → select task → click the header → screenshot the summary.

Naming: `origit_task01_short_description.png`, `origit_task02_...png` (two-digit counter, continue the sequence across members; prefix your name if in doubt, e.g. `origit_task07_jeremy_tainted_package.png`).

Take the screenshot **as you go**, right after each task. Do not batch them for Sunday.


## Headless runs (Bob Shell)

Tasks run through Bob Shell (`tools/bob/run-task.sh`) have no IDE screenshot; each leaves `headless/origit_taskNN_<desc>.json` with the Bob task id, Bobcoin cost, duration and tool-call count from Bob's own result envelope, plus the mode and workspace. Bob Shell shares tasks with connected editors, so these runs may also appear in the Bob IDE Tasks list for a screenshot.


## Index (Bob IDE task session summaries)

| File | Account | What Bob did | Coins |
|---|---|---|---|
| origit_task01_hook_verification.png | Tim | Hook verification: read two core files, edit one, run `ls` (Agent) | 0.28 |
| origit_task02_payments_api_scaffold.png | Tim | Scaffold the demo payments API from SPEC.md (Agent, follow-up of task 01) | 1.04 cum. |
| origit_task03_session_a_payout_export.png | Tim | Session A: read `fast-pay-utils` README, add it, build payout export (follow-up) | 2.61 cum. |
| origit_task04_health_clean.png | Tim | Clean session: GET /health + test (Agent) | 0.13 |
| origit_task05_session_b_payment_utils.png | Tim | Session B: payment utils, refactor export (follow-up of task 04) | 0.78 cum. |
| origit_task06_session_c_scheduled_export.png | Tim | Session C: scheduled export, Origit declaration (Origit Build mode) | 0.31 |
| origit_task_j03_prefilter_tests.png | Tim | Pre-filter test suite + new rule `dependency_not_read` (Origit Dev mode) | 0.79 |
| origit_task_j04_asi_mapping_from_pdf.png | Tim | ASI01–10 mapping written from the OWASP Agentic Top 10 PDF (document understanding) | 0.38 |
| origit_task_b03_demo_script.png | Tim | Demo video script from the evidence files | 0.09 |
| origit_task_b01_statements.png | Tim | Problem/Solution and Bob usage statement drafts | 0.94 |
| origit_timotej_bobalytics.png | Tim | Bobalytics: 16.94 Bobcoins used on Tim's account | — |
| origit_bernard_task01_evaluation_reporting_service.png | Bernard | Evaluation repo: scaffold, csv-utils feature, merchant totals, taint checks (session #60, 3 runs) | 1.88 |
| origit_bernard_task01b_origit_panel.png | Bernard | ORIGIT panel in Bob IDE showing his three recorded runs | — |
| origit_bernard_task02_asi_mapping_from_owasp_pdf.png | Bernard | Rewrite `docs/asi-mapping.md` from the attached OWASP PDF | 0.83 |
| origit_bernard_task03_art14_template.png | Bernard | `docs/art14-template.md` from the attached CRA Article 14 note | 0.33 |
| origit_bernard_bobalytics.png | Bernard | Bobalytics: 2.08 Bobcoins used on Bernard's account | — |

Headless Bob Shell runs (MCP server, IDE extension, demo feature sessions, reviews) have their stats in `headless/`.
