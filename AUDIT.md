# Pre-Publication Audit

Final quality pass before this repository is shown to finance recruiters and, potentially,
CFOs or finance directors reviewing it ahead of an interview. Audited on 2026-07-06 against
that audience: someone who knows FP&A well and will scrutinize the numbers and the logic,
not just the code.

Method: every file in the repo was read (README, all of `output/`, all of `agents/`,
`orchestrator.py`, `tests/`, `data/*.py`, `docs/`), except `data/ground_truth.md`, which was
only exercised through the existing validators. Every figure in the executive summary was
recomputed from `output/variance_table.csv` and `output/forecast.csv` with pandas. The full
git history was scanned for secrets. The complete pipeline was re-run end to end and diffed
against the committed outputs. All four validators were run and pass.

Findings are labeled by section (N = numbers, D = dead code, V = visualization,
S = security, R = reproducibility, W = writing) with a severity: **fix** (must change
before publishing) or **minor** (worth fixing while in there).

---

## 1. Numerical and logical consistency

**What was verified and reconciles exactly (no drift found):**

- Every money figure and percentage in `output/executive_summary.md` traces to
  `output/variance_report.md` or `output/forecast_report.md`: the Falcon overrun
  (EUR2.08M / +26.6% vs +2,077,456 / +26.6%), the FX dip (EUR197,000 / -9.3% vs
  -196,953 / -9.3%), the Marketing savings (EUR81,464 / -16.4%, exact), the IT incident
  (EUR24,116 / +158.1%, exact), the three largest follow-up items (407k / +15.7%,
  389k / +8.3%, 225k / -14.8% vs +407,217, +388,823, -224,810), and the follow-up range
  "EUR55,000 to EUR407,000" (actual bounds 55,202 and 407,217).
- The forecast headline recomputes from `output/forecast.csv` to the euro: revenue
  22,613,628, costs 11,782,899, net 10,830,729, margin 47.9%. Per-BU revenue growth
  (+6.4 / +6.1 / +5.1 / +4.6) matches the report's revenue rows.
- Cross-artifact counts agree everywhere: 20 material items (4 evidence-grounded, 16
  unexplained), 33 flagged month-rows + 1 suspected data error = the 34 rows the QA report
  reconciles and the 34 normalizations in the forecast audit trail.

**Issues found:**

- **N1 (fix).** The executive summary frames a 30-month analysis as current-year.
  "The group's year-to-date performance" (opening) and "Sixteen further variances this
  year" (Follow-Up section) are wrong: the material variances span June 2024 to April
  2026. A CFO reads "this year" as 2026 and immediately trips over a November 2024 IT
  incident three paragraphs later. Rewrite the time framing to "over the period under
  review" or name the window.
- **N2 (fix).** "No cost-saving or overrun programme was still running at the July 2026
  cutoff" (executive summary, closing). The cutoff is June 2026, the last closed month;
  July is the first forecast month. `output/forecast_report.md` states "Last closed month:
  June 2026". Small, but it is exactly the kind of slip a finance reviewer catches.
- **N3 (fix).** The Marketing savings paragraph states the episode window as "April
  2025-February 2026" and, in the same breath, the cause as in-housing "starting July
  2025". The cause postdates the stated window's start by three months, with no comment.
  The reason is known and documented in PROGRESS.md (the episode detector bridges adjacent
  same-direction noise months, so the detected span is wider than the programme), but the
  reader of the summary gets none of that. Add one honest sentence: the underspend
  concentrates from July 2025, when the programme started, and the wider detected window
  includes adjacent months drifting the same direction.
- **N4 (minor).** "the one clearly favorable story in this period's variances" overstates:
  8 of the 20 material rows are favorable (most unexplained). It is the only favorable
  variance with a documented driver. Reword to say that.
- **N5 (minor).** "roughly EUR81,464" prefixes "roughly" to an exact table figure. Either
  drop "roughly" or round the number.
- **N6 (fix).** Internal contradiction between committed artifacts: `output/pipeline_log.md`
  shows the Narrative step FAILED (no credentials), while `output/board_pack.md` from the
  same run says "Narrative commentary: included below". The orchestrator
  (`orchestrator.py`, `assemble_board_pack`) includes any pre-existing
  `output/executive_summary.md` regardless of whether it was regenerated this run. Beyond
  the cosmetic contradiction, this is a real stale-narrative risk: a summary from a prior
  month's numbers would be silently packaged with this month's tables. Fix: the pack
  should state whether the narrative was generated this run or carried over from an
  earlier one, based on the step's actual result.
- **N7 (minor).** `output/data_quality_report.md` section 1 lists the same correction
  twice ("Digitial" -> Digital, 2026-04) because BU-name correction runs before
  de-duplication and the duplicated row is corrected twice, and the console count says
  "8 typos corrected" where 7 distinct typos exist. Not wrong, but it reads as sloppy in a
  data-quality report of all places. De-duplicate the log entries.

## 2. Errors, dead code, unused files, placeholders

- **D1 (fix).** `output/sample_report.md` is a two-line leftover placeholder ("Generated by
  the Narrative Agent once the pipeline is built (Phase 3+)"), superseded by
  `executive_summary.md` and `board_pack.md`. Delete it and update the repo-structure
  listing in CLAUDE.md section 6, which still names it.
- **D2 (minor).** `docs/.gitkeep` is stale (docs/ has real content) and
  `output/dashboard/` contains nothing but a `.gitkeep` and is referenced nowhere. Delete
  both; the charts live in `docs/`.
- **D3 (minor).** Unused parameters: `render_report(fc, adjustments, growth, df, ...)` in
  `agents/forecast_agent.py` never uses `growth` or `df`; `run_step(script, description)`
  in `orchestrator.py` never uses `description`. Harmless, but trivially cleaned.
- **D4 (minor).** PROGRESS.md ends with two contradictory "Next step" paragraphs: the
  first (line 149) correctly says the README pass is done; the second (line 151) is a
  stale leftover claiming "Problem/Solution/Results sections are still empty headers".
  Delete the stale one.
- **D5 (minor).** README's Option B links to `github.com/anthropics/anthropic-cli`. This
  session could not verify the URL resolves. Verify before publishing (Stage 2 will
  attempt; if unverifiable, keep the `ant auth login` instructions but drop or soften the
  hyperlink).
- No TODO/FIXME/stub functions found anywhere in the code. No other placeholders.

## 3. Visualization review

**Inventory today:** two PNGs in `docs/` (`variance_highlights.png`: a horizontal diverging
bar of all 20 material variances, blue favorable / red unfavorable, hatched = no documented
driver; `forecast_outlook.png`: grouped bars of Q3 2026 revenue / total costs / net result
by month), plus a Mermaid architecture diagram embedded in the README. There is no
dashboard.

- **V1 (fix).** There is no budget-to-actual bridge anywhere, and that is the one chart an
  FP&A audience expects from a variance analysis. The conventional format for "we were at
  budget X, these drivers moved us, we landed at actual Y" is a waterfall: start bar
  (budget net result), one floating block per named driver, a block for
  material-but-unexplained items, a residual "all other" block, end bar (actual net
  result), reconciling exactly. Build it for FY2025 (the year containing three of the four
  evidence-grounded stories: Falcon, FX, and the 2025 portion of the Marketing savings) at
  group net-result level, from `output/variance_table.csv`. Footnote that the excluded
  Production November 2025 data-entry row is out of the walk pending correction, which
  showcases the project's core discipline right on the flagship chart.
- **V2 (fix).** `variance_highlights.png` plots signed variance vs budget on the x-axis
  with favorable/unfavorable as color. Because cost and revenue lines are mixed, direction
  and color disagree: a favorable COGS variance points left while a favorable revenue
  variance points right, and the reader has to resolve the conflict row by row. For a
  finance audience, encode P&L impact (favorable always one direction) or sort by category.
  Also, finance convention colors favorable green and unfavorable red; blue/red reads as a
  generic diverging palette, not a P&L. Keep the hatched-vs-solid evidence distinction; it
  is the chart's genuinely good idea and visualizes the project's differentiator.
- **V3 (minor).** `forecast_outlook.png` plots net result as a third bar next to revenue
  and costs, which is redundant (net = revenue - costs), and shows no prior-year
  comparison even though "+5.5% vs PY" is the report's headline. A small PY reference
  would earn its place. Acceptable as a secondary chart either way.
- **V4 (fix).** Neither PNG can be regenerated: no chart-generation script was ever
  committed (verified against the full git history). For a repo whose whole pitch is a
  reproducible pipeline, the charts must come from a committed script reading the pipeline
  outputs. Add `make_charts.py` and reference it in the README.

## 4. Security and hygiene

- **Clean: no secrets in git history.** All patches across all commits were scanned for
  key material (`sk-ant-` tokens, key/token assignments, private key blocks, bearer
  headers). The only matches are the README's own placeholder examples (`sk-ant-...`).
  No `.env` or credential file was ever committed. Nothing needs rotating.
- `agents/narrative_agent.py` never hardcodes a credential (bare `anthropic.Anthropic()`;
  resolves env var or OAuth profile), and `agents/qa_agent.py` structurally verifies no
  other agent references an external AI provider. Both confirmed by reading the code, not
  just the docs.
- **S1 (fix).** `.gitignore` covers `__pycache__/`, `*.pyc`, `.venv/`, `venv/` but not
  `.env`. Anyone following the README's Option A on a fork could commit their key with one
  careless `git add .`. Add `.env` and `.env.*`.

## 5. Reproducibility

**Verified working:** the full pipeline was re-run end to end on this machine
(`.venv/Scripts/python.exe orchestrator.py`). Every committed output reproduced
byte-for-byte; the only diff was the two run timestamps in `pipeline_log.md` and
`board_pack.md`. The Narrative step fails cleanly without credentials, exactly as the
README says it will, and the QA and pack steps handle it. All four validators pass. No
hardcoded absolute paths exist anywhere; all paths are repo-root-relative.

- **R1 (fix).** The README's "Run it yourself" commands are Windows-only
  (`.venv/Scripts/...`; on macOS/Linux the venv layout is `.venv/bin/...`) and use `&&`,
  which fails in stock Windows PowerShell 5.1. Give short per-OS blocks.
- **R2 (minor).** No Python version requirement is stated in the run section (the pinned
  pandas 3.0.3 / numpy 2.5.1 need a recent interpreter; the project runs on 3.12). State
  "Python 3.12 (tested)".
- **R3 (minor).** The scripts assume they run from the repo root (all paths are relative).
  The README's commands already do this; add the assumption in one clause so nobody runs
  an agent from inside `agents/`.
- **R4.** Same as V4: charts are not regenerable. Fixed by the committed chart script.

## 6. Writing quality

- **W1 (fix): em dashes.** 279 across the user-facing files: README.md 30,
  variance_report.md 41, forecast_report.md 55, board_pack.md 122 (it embeds the others),
  executive_summary.md 11, qa_report.md 12, data_quality_report.md 7, sample_report.md 1.
  Because every `output/*.md` except the executive summary is generated, the fix belongs
  in the template strings of `agents/ingestion_agent.py`, `agents/variance_agent.py`,
  `agents/forecast_agent.py`, `agents/qa_agent.py`, `agents/grounding_check.py`, and
  `orchestrator.py`, followed by a pipeline re-run; editing the outputs alone would be
  undone by the next run. The executive summary is edited directly, and the Narrative
  Agent's system prompt gets a no-em-dash style rule so future generated runs comply too.
  The report titles ("Variance Report — EventCo...") are included. Validator-load-bearing
  phrases ("no clear driver identified", "one-off", "episode", "data entry error", section
  headers, the signed-number table format) must survive the rewrite; the validators will
  be re-run to prove it.
- **W2 (fix): buzzwords.** Exactly one hit in all user-facing text: "robust growth" in
  forecast_report.md ("Forecast = seasonal base × robust growth"), generated by
  `agents/forecast_agent.py`. "Robust" is defensible as a statistics term (the median is a
  robust estimator) but lands as filler to this audience; "median year-over-year growth"
  says the same thing concretely. No instance of leverage / streamline / unlock / seamless
  / cutting-edge / innovative / game-changer / holistic / dynamic / agile / synergy /
  data-driven / actionable insights / move the needle anywhere.
- **W3 (minor): canned openers and rhythm.** The executive summary opens with "mixed but
  manageable", a stock phrase that says nothing a CFO can act on, and closes on "a
  reminder that not everything material this year has been bad news", which is chatty for
  a board pack. The README's Architecture section runs several near-identical long
  paragraphs in a row. Vary during the Stage 2 rewrite.
- **W4 (minor): vague claims.** Few, which is to the project's credit. The two worth
  tightening: README's "repetitive, slow, and inconsistent between analysts" (fair as
  framing, but the Problem section can name the two failure modes even more concretely up
  front) and the summary's "the one clearly favorable story" (N4). No unbacked numeric
  claims found; every number in the README's Results section traces to the reports.
- **W5 (fix): the README hides the project's documented limitations.** PROGRESS.md
  honestly records that the ingestion agent's informational IQR tier surfaced only 5 of 11
  anomaly-months, that the narrative trap check is keyword-based with a known evasion gap,
  and that the committed executive summary was hand-written in-session (disclosed in the
  file itself but not in the README). Intellectual honesty is this project's stated design
  principle; the README should carry a short "Known limitations" section saying these
  things plainly rather than leaving them for the reader to discover in the logs.

Note on scope: CLAUDE.md and PROGRESS.md are internal working-memory documents, not
recruiter-facing deliverables, and keep their current style except for the updates this
audit itself requires.

---

## Stage 2 fix list (in order)

1. N6: orchestrator distinguishes "generated this run" from "carried over" narrative;
   D3 dead parameters; N7 duplicate typo-log entries.
2. S1: add `.env` / `.env.*` to `.gitignore`.
3. D1, D2, D4: delete `output/sample_report.md`, stale `.gitkeep`s and `output/dashboard/`;
   fix PROGRESS.md's duplicated stale paragraph; update CLAUDE.md section 6.
4. W1, W2: rewrite generator template strings (no em dashes, no "robust growth"),
   add the no-em-dash rule to the narrative system prompt.
5. N1-N5, W3: rewrite `output/executive_summary.md` (framing, cutoff month, savings-window
   sentence, wording), keeping every figure identical.
6. V1, V2, V4 (and V3 if cheap): committed `make_charts.py` producing a FY2025 group
   net-result budget-to-actual waterfall (new flagship), a fixed variance-highlights chart,
   and the forecast chart; README references updated.
7. R1-R3: README "Run it yourself" per-OS commands, Python version, run-from-root note.
8. W4, W5, D5: README final rewrite with a Known limitations section; verify or soften the
   `ant` CLI link.
9. Re-run the full pipeline and all four validators; confirm zero em dashes and zero
   buzzwords remain in README and `output/*.md`; update PROGRESS.md and CLAUDE.md; commit.
