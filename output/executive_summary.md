<!-- Provenance note: agents/narrative_agent.py is fully built and calls claude-sonnet-5
via the Anthropic API (see the script and README.md for how to run it). This particular
file was instead written directly in an interactive Claude Code session (Claude Fable 5,
2026-07-06), because the script's own API/OAuth credentials were not available on the
local machine at the time. The same strict-grounding system prompt from the script was
followed by hand: every figure below is sourced from output/variance_report.md and
output/forecast_report.md, and this file has been checked with tests/validate_narrative.py.
Revised in the 2026-07-06 pre-publication audit (framing and style only; every figure
unchanged and re-validated). Anyone running the pipeline end to end should re-run
agents/narrative_agent.py once credentials are set up, to get the authoritative,
reproducible output from the pinned model. -->

# Executive Summary: EventCo Budget vs Actual & Rolling Forecast

Three stories dominate the variances over the 30 months under review: a EUR2.08 million
cost overrun on a single client project, an unfavorable currency swing on an international
contract, and a cost-savings programme that ran ahead of plan. The rolling forecast points
to continued top-line growth into the third quarter of 2026, with the group margin holding
at 47.9% over the forecast period.

## Variance Highlights

**Production COGS, April to June 2025: EUR2.08 million over budget (+26.6%).** The largest
variance in the period, tied to the Falcon product-launch event in Riyadh. The client
requested a major on-site scope expansion during the build week, and the resulting overtime
crews, additional staging and expedited freight were all booked at premium rates. A change
order was signed with the client, but it recovered only part of the overrun, and the margin
impact has been flagged to group controlling.

**Digital revenue, September 2025: roughly EUR197,000 under budget (-9.3%).** This is a
currency effect, not a shortfall in delivery. The NovaTech roadshow contract is invoiced in
USD, and the euro strengthened sharply against the dollar during the month, translating the
same contracted revenue into fewer euros. Delivered scope and client commitment were
unchanged, and the associated delivery costs are euro-denominated and unaffected.

**Marketing opex, April 2025 to February 2026: EUR81,464 under budget (-16.4%),
favorable.** Media buying and content creation moved in-house from July 2025, ending two
external agency retainers, and the business unit controller confirmed in September that the
savings were tracking ahead of plan. One caveat on the dates: the reported window is the
full run of consecutive under-budget months grouped by the episode test, and it starts
three months before the programme did. The months before July drifted below budget in the
same direction but have no documented driver of their own. This is the only favorable
variance in the period with a documented cause.

**Back-Office IT opex, November 2024: EUR24,116 over budget (+158.1%).** An emergency
storage cluster failure in the Paris server room required expedited replacement hardware
and vendor licenses outside the normal purchasing cycle. A one-off cost with an insurance
claim filed against it, not the start of a trend.

## Items Requiring Follow-Up

Sixteen further variances across the period are large enough to be material, ranging from
roughly EUR55,000 to EUR407,000 in absolute impact, both favorable and unfavorable, but
have no documented driver in the business notes log reviewed for this report. The three
largest are Production COGS in April 2026 (roughly EUR407,000 over budget, +15.7%),
Production revenue that same month (roughly EUR389,000 above budget, +8.3%, favorable), and
Digital revenue in January 2025 (roughly EUR225,000 under budget, -14.8%). These are
numerically material but genuinely unexplained. Each is recommended for follow-up with the
relevant business unit controller rather than assigned a cause here.

Separately, a data entry issue was identified in Production's November 2025 revenue figure
and has been excluded from this analysis pending correction at source.

## Rolling Forecast

For July to September 2026, the group is forecast to generate roughly EUR22.6 million in
revenue against roughly EUR11.78 million in costs, for a net result of about EUR10.83
million, a 47.9% margin. Revenue growth versus the same quarter last year varies by
business unit: Back-Office +6.4%, Production +6.1%, Marketing +5.1%, and Digital +4.6%.

The forecast is built from each business unit's own results in the same quarter last year,
adjusted for its typical year-over-year growth rate, rather than from budget. One-off
events, including the Falcon cost overrun and the Back-Office IT incident above, are
deliberately excluded from that base so they are not projected forward as if they were
normal, recurring activity. The Marketing savings programme is treated the same way: it had
already concluded before the forecast cutoff of June 2026, the last closed month, so its
effect is not carried into the outlook, consistent with how any other concluded programme
is handled.

No cost-saving or overrun programme was still running at the June 2026 cutoff, so this
quarter's outlook reflects normal seasonal business growth with no special adjustment
carried forward. The sixteen undocumented variances above are the main open item going
into the next close.
