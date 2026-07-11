"""Narrative Agent.

Writes the board-level executive commentary for EventCo's monthly Budget vs
Actual + rolling forecast pack, from the two upstream reports:
output/variance_report.md and output/forecast_report.md.

This is the first agent in the pipeline that calls an LLM, and deliberately
so. The Ingestion, Variance, and Forecast agents are all plain deterministic
Python: materiality thresholds, evidence grounding, and trend normalization
are decisions that need to be auditable and reproducible — the same input
must always produce the same threshold check or the same normalized
history, and a reviewer must be able to read the code and know exactly why
a number was flagged or adjusted. None of that holds for writing a coherent
executive narrative from already-computed, already-grounded numbers: turning
a variance table and a forecast table into readable prose for a CFO is a
language task, not an arithmetic one, and that is exactly what an LLM is
for. The reasoning that could hallucinate a cause has already happened
upstream in the Variance Agent (which only cites evidence it can point to,
or says "no clear driver identified"); this agent's only job is to write
clearly from those already-grounded conclusions — so it is explicitly
instructed never to introduce a new number, cause, or claim of its own.

Model: claude-sonnet-5. The judgment calls (materiality thresholds, evidence
grounding, forecast normalization) are already resolved by the upstream
agents; this step is disciplined prose generation from structured, cited
inputs, not open-ended reasoning. Claude Fable 5 (reserved per dev/CLAUDE.md
section 5 for the hard architectural/methodology calls) would be overkill
and far more expensive for a formatting/writing pass; Haiku 4.5 was
considered but rejected because this is the single deliverable recruiters
will actually read line by line — Sonnet 5's writing quality is worth the
small cost step-up over Haiku for a report generated once a month.

Authenticates via the default Anthropic() client construction, which
resolves ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, or an `ant auth login`
OAuth profile (whichever is available) — no key is ever hardcoded. See
README.md for setup, including the OAuth option for callers without a
separate metered API key.

Output: output/executive_summary.md

Run: .venv/Scripts/python.exe agents/narrative_agent.py
"""

import datetime

import anthropic

VARIANCE_REPORT_PATH = "output/variance_report.md"
FORECAST_REPORT_PATH = "output/forecast_report.md"
OUTPUT_PATH = "output/executive_summary.md"

MODEL = "claude-sonnet-5"
MAX_TOKENS = 4096

SYSTEM_PROMPT = """You are a senior FP&A writer producing the executive commentary section of \
EventCo's monthly Budget vs Actual and Rolling Forecast board pack. Your audience is the CFO \
and the board — not analysts, not engineers.

You will be given two source documents: a Variance & Root-Cause Report and a Rolling Forecast \
Report. Both were produced by deterministic analysis: every variance, every materiality \
threshold, every evidence citation, and every forecast figure in them has already been computed \
and checked. Your only job is to turn those already-grounded conclusions into clear, readable \
prose. You are not being asked to analyze the business yourself.

STRICT GROUNDING RULES — these are the most important instructions in this prompt:
- Only state figures, causes, and conclusions that are explicitly present in the two source \
documents below. Never invent, estimate, or infer a number, cause, or claim that is not in the \
source text.
- You may lightly round a monetary figure for readability (for example, writing "roughly \
EUR2.08 million" for a source value of "EUR2,077,456") as long as the rounded figure clearly \
derives from the source number and preserves its sign and order of magnitude. Never alter, \
combine, or extrapolate figures beyond what is given.
- Where the Variance Report explicitly says "no clear driver identified" for a material \
variance, you must preserve that honesty. Describe the variance as material but undocumented \
or unexplained, and note that it warrants follow-up with the business unit. Do NOT invent a \
plausible-sounding cause, and do NOT phrase it in a way that reads as confidently explained — a \
reader must come away understanding that this specific number has no documented driver yet.
- The report also lists a row excluded as a suspected data entry error. Mention only that a \
data quality issue was identified and excluded pending correction at source. Do not narrate it \
as a business event or attempt to explain it as if it were a real variance.
- Cover the favorable variance(s) as prominently as the unfavorable ones — the report should \
not read as one-sided ("everything is bad"). Prioritize by materiality (largest EUR impact \
first), not by favorable/unfavorable.

STYLE:
- Plain business English. No AI or technical jargon anywhere ("agent", "pipeline", "model", \
"LLM", "automated" or similar words must not appear) — write as a human FP&A analyst would.
- Never use an em dash anywhere in the output; punctuate with commas, periods, or colons \
instead. Avoid filler words like "leverage", "streamline", "seamless", "robust", "holistic", \
"data-driven" — say the concrete thing.
- Concise: aim for roughly 500-800 words of prose, using short section headers to aid scanning, \
not a wall of text and not a bullet-only outline.
- Structure: (1) a short 2-4 sentence opening on overall performance and outlook, (2) a \
"Variance Highlights" section covering the material variances with their evidence, largest \
impact first, (3) an "Items Requiring Follow-Up" section for the material variances that have \
no documented driver, (4) a "Rolling Forecast" section summarizing the outlook and any \
methodology judgment calls worth flagging to the reader, (5) an optional one-sentence closing \
line. Do not add a section for the excluded data-error row — one sentence in an appropriate \
place is enough.
- Do not fabricate a title, company boilerplate, or sign-off beyond a simple heading."""


def build_user_message(variance_report, forecast_report):
    return f"""Here are the two source reports. Write the executive commentary from them.

<variance_report>
{variance_report}
</variance_report>

<forecast_report>
{forecast_report}
</forecast_report>

Write the executive commentary now, following the grounding rules and structure in your \
instructions. Output only the commentary itself (starting with a heading), no preamble."""


def main():
    with open(VARIANCE_REPORT_PATH, encoding="utf-8") as f:
        variance_report = f.read()
    with open(FORECAST_REPORT_PATH, encoding="utf-8") as f:
        forecast_report = f.read()

    # Bare Anthropic() resolves credentials in order: ANTHROPIC_API_KEY,
    # ANTHROPIC_AUTH_TOKEN, then an active `ant auth login` OAuth profile —
    # so this works whether the caller has a metered API key or is
    # authenticating through their Claude subscription via OAuth. Never
    # hardcode a key here.
    client = anthropic.Anthropic()
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            output_config={"effort": "medium"},
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": build_user_message(variance_report, forecast_report)},
            ],
        )
    except anthropic.AuthenticationError:
        raise SystemExit(
            "No Anthropic credentials found (rejected). Either set ANTHROPIC_API_KEY, or run "
            "`ant auth login` to authenticate via OAuth (uses your Claude subscription "
            "instead of a separate metered API key). See README.md for setup."
        )
    except TypeError as e:
        # When NO credential source exists at all (not even an invalid one),
        # the SDK fails at header-construction time with a plain TypeError
        # rather than AuthenticationError — a different failure shape for the
        # same underlying problem, so it needs its own catch here.
        if "Could not resolve authentication method" not in str(e):
            raise
        raise SystemExit(
            "No Anthropic credentials configured. Either set ANTHROPIC_API_KEY, or run "
            "`ant auth login` to authenticate via OAuth (uses your Claude subscription "
            "instead of a separate metered API key). See README.md for setup."
        )

    if response.stop_reason == "refusal":
        raise SystemExit("Model declined to generate the summary (stop_reason=refusal).")

    narrative = next(b.text for b in response.content if b.type == "text")

    header = (
        f"<!-- Generated by agents/narrative_agent.py using {MODEL} on "
        f"{datetime.date.today():%Y-%m-%d}. Source: output/variance_report.md and "
        f"output/forecast_report.md. Never reads data/ground_truth.md. -->\n\n"
    )
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(header + narrative.strip() + "\n")

    print(f"Input tokens: {response.usage.input_tokens}, output tokens: {response.usage.output_tokens}")
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
