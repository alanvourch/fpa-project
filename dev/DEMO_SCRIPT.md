# Demo video: script + shot-by-shot storyboard

Target: 60-90 seconds, screen recording + voiceover (or silent with captions,
alternative text provided per shot). Audience: the same as the showcase, CFOs
and finance recruiters. One idea per shot, outcome first, zero jargon. Words
per shot are sized for a calm ~2.4 words/second delivery.

## Pre-flight (do once, before recording)

1. Set up narrative credentials (`ant auth login` or `ANTHROPIC_API_KEY`) so
   the Narrative step visibly runs instead of logging "did not complete".
   Re-run `.venv\Scripts\python.exe agents/narrative_agent.py` once, then
   `orchestrator.py` once, and skim the fresh executive summary for quality
   before filming (the validator must pass: `tests/validate_narrative.py`).
2. Screen at 1920x1080, 125% Windows scaling off for crisp text. Terminal:
   PowerShell, font 16-18pt, dark theme. Editor for markdown preview: VS Code.
3. Close everything else. Hide the taskbar clock (notifications off).
4. Have these files pre-opened in background tabs, in order:
   `data/eventco_monthly.csv` (Excel or VS Code), `output/data_quality_report.md`
   (preview), `output/board_pack.md` (preview), `output/bu_reports/production.pdf`,
   and the live showcase in a browser tab.
5. The run is deterministic, so a botched take costs nothing: re-run and refilm.

## Storyboard

| # | Time | On screen | Action | Voiceover (or caption) |
|---|---|---|---|---|
| 1 | 0:00-0:08 | The raw CSV, scrolled to the November 2025 Production row | Slow scroll, then hover-highlight the 52,243,583 cell for a beat | "This is the export every finance team knows. Four date formats, typos in unit names, and one revenue figure ten times too big." |
| 2 | 0:08-0:14 | Terminal, empty prompt | Type `.venv\Scripts\python.exe orchestrator.py`, press Enter | "One command runs the whole monthly close." |
| 3 | 0:14-0:28 | Terminal output scrolling: ingestion counts, "Material items: 20", forecast horizon, "4 BU one-pagers", "QA checks: 8 passed" | Let it run; do not speed up, it is fast enough | "It cleans the file, measures 840 budget gaps, explains only what the evidence supports, refreshes the forecast, and writes the reports." |
| 4 | 0:28-0:38 | `output/data_quality_report.md` preview, section 6 | Scroll straight to the flagged data-error table, highlight the row | "That fifty-two million? Flagged as a data entry error, not narrated as growth. The ops system agrees: a normal month, eighteen projects delivered." |
| 5 | 0:38-0:52 | `output/board_pack.md` preview | Scroll: opening of the executive summary, the FY2025 bridge chart (switch briefly to `docs/variance_bridge_2025.png`), then the DRAFT banner and sign-off block | "The pack reads like a controller wrote it. Sixteen of twenty material gaps say, honestly, no documented driver, follow up. And it ends the only acceptable way: pending human sign-off." |
| 6 | 0:52-1:04 | `output/bu_reports/production.pdf`, full page visible | Slow zoom on "What drove it": headcount vs rate, volume vs price | "Each business unit gets one page: what drove payroll, people or pay rates. What drove revenue, volume or price. Ready to hand to the manager." |
| 7 | 1:04-1:15 | The live showcase page, one smooth scroll; hold on the hero line | End card fades in: `alanvourch.com/fpa-project` + "Alan Vourc'h" | "AI writes only the words. Every number is a checkable calculation, and a human signs before anything moves. The full demo is at alanvourch.com." |

## Silent-version captions

Use the voiceover lines as on-screen captions, bottom third, one line at a
time, white on a dark translucent bar. Trim each to its first sentence if a
shot feels crowded.

## Retake checklist

- [ ] The 52M cell highlight in shot 1 is readable at 100% zoom
- [ ] Shot 3 shows "QA checks: 8 passed, 0 failed" before cutting
- [ ] Shot 5 lingers at least 2 seconds on the DRAFT / sign-off block
- [ ] Shot 6 shows the page top (scorecard) before zooming to drivers
- [ ] No personal notifications, bookmarks bar hidden in shot 7
- [ ] Total under 80 seconds; if over, cut shot 4's second sentence first
