"""Orchestrator.

Chains the pipeline end to end: Ingestion -> Variance & Root-Cause ->
Forecast -> Narrative -> QA/Reviewer -> assembled pack. Each step is a
separate script, run as its own process (the same way a finance ops team
would run a sequence of jobs) so every step's own console output, and every
intermediate file it writes, stays independently inspectable — nothing is
hidden inside one big in-memory pipeline.

This is deliberately NOT a fully autonomous, fire-and-forget pipeline.
Given the sensitivity of financial data and the consequences of a wrong
number reaching a board pack, this project's position is that a human must
stay in the loop:

- The assembled pack and the QA report are always written as drafts. There
  is no step anywhere in this pipeline that sends a report to anyone. The
  human running this script decides what happens to output/board_pack.md
  after reading it and output/qa_report.md.
- The Narrative Agent is the only step that calls an external AI provider,
  and only ever receives the two already-aggregated summary reports (see
  agents/qa_agent.py's data-governance checks, which verify this
  structurally on every run) — never the raw dataset, never anything
  client-identifying beyond what the Variance Agent already aggregated to
  BU/month level.
- If the Narrative Agent can't run (no API credentials configured), the
  orchestrator does not stop the rest of the pipeline or fail silently — it
  logs the gap plainly and the assembled pack says so explicitly, rather
  than pretending a narrative exists when it doesn't.

Output: output/pipeline_log.md (what ran, in what order, with what result)
        output/board_pack.md   (the assembled draft pack)

Run: .venv/Scripts/python.exe orchestrator.py
"""

import datetime
import os
import subprocess
import sys

PIPELINE_LOG_PATH = "output/pipeline_log.md"
BOARD_PACK_PATH = "output/board_pack.md"

VARIANCE_REPORT_PATH = "output/variance_report.md"
FORECAST_REPORT_PATH = "output/forecast_report.md"
NARRATIVE_PATH = "output/executive_summary.md"
QA_REPORT_PATH = "output/qa_report.md"

# (script, description, halt_pipeline_on_failure). The narrative step is the
# one expected point of failure in an environment with no LLM credentials
# configured — it must not take the rest of the pipeline down with it.
STEPS = [
    ("agents/ingestion_agent.py", "Data Ingestion", True),
    ("agents/variance_agent.py", "Variance & Root-Cause", True),
    ("agents/forecast_agent.py", "Rolling Forecast", True),
    ("agents/narrative_agent.py", "Narrative (LLM)", False),
    ("agents/qa_agent.py", "QA/Reviewer", False),
]


def run_step(script, description):
    result = subprocess.run(
        [sys.executable, script],
        capture_output=True, text=True,
    )
    return result


def load_if_exists(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()


def assemble_board_pack(log_entries):
    now = datetime.datetime.now()
    narrative_status = "included below" if os.path.exists(NARRATIVE_PATH) else (
        "NOT GENERATED THIS RUN — the Narrative Agent needs an Anthropic API key or "
        "`ant auth login` OAuth profile configured. Run `agents/narrative_agent.py` "
        "separately once available, then re-run the orchestrator."
    )

    lines = [
        "# EventCo Budget vs Actual & Rolling Forecast — Draft Board Pack",
        "",
        f"Assembled {now:%Y-%m-%d %H:%M} by `orchestrator.py`.",
        "",
        "> ## DRAFT — PENDING HUMAN SIGN-OFF",
        "> This pack was assembled automatically but is **not approved for distribution**.",
        "> No step in this pipeline sends this document anywhere. Review this pack and",
        f"> `{QA_REPORT_PATH}` in full, resolve anything flagged, and sign off below",
        "> before this leaves your hands.",
        "",
        f"**Narrative commentary:** {narrative_status}",
        "",
        "---",
        "",
        "## 1. Variance & Root-Cause",
        "",
        load_if_exists(VARIANCE_REPORT_PATH) or "*(not available — the Variance Agent did not run successfully this session)*",
        "---",
        "",
        "## 2. Rolling Forecast",
        "",
        load_if_exists(FORECAST_REPORT_PATH) or "*(not available — the Forecast Agent did not run successfully this session)*",
        "---",
        "",
        "## 3. Executive Narrative",
        "",
        load_if_exists(NARRATIVE_PATH) or "*(not generated this run — see status above)*",
        "---",
        "",
        "## 4. QA Review",
        "",
        load_if_exists(QA_REPORT_PATH) or "*(not available — the QA Agent did not run successfully this session)*",
        "---",
        "",
        "## Sign-off",
        "",
        "This pack is not final until a human reviewer completes the line below.",
        "",
        "- Reviewed by: ______________________",
        "- Date: ______________________",
        "- Approved for distribution: [ ] Yes  [ ] No — changes requested (see notes)",
        "- Notes: ______________________",
        "",
    ]
    return "\n".join(lines) + "\n"


def main():
    log_entries = []
    failures = []

    for script, description, halt_on_failure in STEPS:
        print(f"--- Running {description} ({script}) ---")
        result = run_step(script, description)
        ok = result.returncode == 0
        print(result.stdout.strip())
        if not ok:
            print(result.stderr.strip())

        log_entries.append({
            "script": script, "description": description,
            "returncode": result.returncode, "ok": ok,
            "stdout": result.stdout.strip(), "stderr": result.stderr.strip(),
        })

        if not ok:
            if halt_on_failure:
                failures.append(description)
                print(f"\nHALTING: {description} failed and is required for downstream steps.\n")
                break
            else:
                print(f"\n{description} did not complete (non-fatal) — continuing.\n")

    now = datetime.datetime.now()
    log_lines = [
        "# Pipeline Run Log", "",
        f"Run at {now:%Y-%m-%d %H:%M} by `orchestrator.py`.", "",
        "| Step | Script | Exit code | Result |",
        "|---|---|---|---|",
    ]
    for entry in log_entries:
        status = "OK" if entry["ok"] else "FAILED"
        log_lines.append(f"| {entry['description']} | `{entry['script']}` | {entry['returncode']} | {status} |")
    log_lines += ["", "## Step output", ""]
    for entry in log_entries:
        log_lines += [f"### {entry['description']}", "", "```", entry["stdout"] or "(no output)", "```"]
        if entry["stderr"]:
            log_lines += ["", "stderr:", "```", entry["stderr"], "```"]
        log_lines.append("")

    with open(PIPELINE_LOG_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines) + "\n")

    if failures:
        print(f"\nPipeline halted: {', '.join(failures)} failed. See {PIPELINE_LOG_PATH}.")
        return 1

    with open(BOARD_PACK_PATH, "w", encoding="utf-8") as f:
        f.write(assemble_board_pack(log_entries))

    print(f"\nWrote {PIPELINE_LOG_PATH} and {BOARD_PACK_PATH}.")
    print(
        "\nPIPELINE COMPLETE — DRAFT ONLY.\n"
        f"Review {BOARD_PACK_PATH} and {QA_REPORT_PATH} before distributing anything.\n"
        "Nothing produced by this run has been sent anywhere outside this repository."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
