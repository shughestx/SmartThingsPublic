---
name: inventory-variance-research
description: >
  Agentic root-cause research for inventory variances at Equity Exchange. Takes the list of
  items with physical count variances (from the monthly variance report at
  secure.perrytonequity.com), then works the list ONE ITEM AT A TIME — investigating purchase
  history, transfers, adjustments, unposted BOLs, unit-of-measure errors, and sister-SKU
  mix-ups — to explain WHY each item is out of balance. Produces an Excel research workbook
  with evidence, a root-cause classification, and a recommended corrective action per item.

  Use this skill whenever Shawn asks to: research the variances, investigate why inventory is
  out of balance, work the variance list, find out why counts don't match, explain the
  shortages/overages, chase down count discrepancies, or reconcile physical counts to the ERP.
  Also trigger on phrases like "why are we short on [item]", "dig into the variances",
  "research why it's not in balance", "what's driving the variance", or any request to go
  item-by-item through count variances — even if he just says "work the variances" or
  "research the variance report." (Note: RUNNING the variance report itself is the
  variance-margin-report skill; this skill is the follow-up investigation of the items on it.)
---

# Inventory Variance Research Agent — Equity Exchange

The monthly variance report tells Shawn WHICH items are out of balance (physical count ≠
on-record units). This skill answers the harder question: WHY. It is an investigation loop —
take the variance list, triage it by dollar impact, then research each item one at a time
against the ERP's transaction evidence until every material variance has either a root cause
or an explicit "needs recount / needs manual review" disposition.

The goal is a workbook Shawn can hand to branch managers and bookkeepers: each line says what
the variance is, what the evidence shows, what caused it, and exactly what to do about it.

## Prerequisites

- Chrome browser automation (Claude in Chrome MCP) — must be connected and logged in to
  https://secure.perrytonequity.com/intranet
- Python 3 with `openpyxl` (`pip install openpyxl --break-system-packages`)
- The variance-margin-report skill's extraction output (or willingness to run that extraction)
- The xlsx skill conventions (for the final workbook)

## Bundled resources

- `references/root-causes.md` — the diagnostic taxonomy: every known cause of a count
  variance, its telltale signature in the data, what evidence to collect, and the standard
  corrective action. **Read this before starting the research loop.**
- `references/intranet-pages.md` — catalog of the intranet pages used for research, with URL
  formats, parameter encoding (including the 16-character padded item key), and reading notes.
  **Read this before navigating.**
- `scripts/triage_variances.py` — deterministic pre-research pass. Parses the extracted
  variance lines, computes dollar impact, runs automated diagnostics (ledger tie-out, shrink
  plausibility, UOM signature, sister-SKU offsets, adjustment flags), and emits a prioritized
  research queue with starting hypotheses.
- `scripts/build_research_workbook.py` — builds the final Excel workbook from the findings
  file.

## The Workflow

### Step 1 — Get the variance list

If a recent extraction already exists from the variance-margin-report skill (the pipe-delimited
item lines), reuse it — ask Shawn if he wants fresh data first. Otherwise pull fresh data:

1. Navigate to `https://secure.perrytonequity.com/intranet/inventory/menuvariancereport.asp`
2. Parameters: Report Date = MM-YYYY for the month being researched, Start/End = first/last
   day of month, **Location = Company Summary**, **Variance Only = ON**, Select Period =
   Year To Date, Report Type = Normal
3. Extract items using the variance-margin-report skill's `extract_items.js` two-phase
   approach (collect into `window._varItems`, retrieve in slices of 10)

Save all lines to a working file `variances.txt`, one pipe-delimited line per item:
```
SKU|Desc|UOM|Cat|BegU|PurU|XfrU|SalU|AdjU|OnRecU|CntU|VarU|Beg$|Pur$|Xfr$|Rev$|Adj$|Cnt$|Margin$|MarginPct
```

### Step 2 — Triage before researching

Run the triage script — never start researching from an unsorted list. Research time is the
scarce resource, so the biggest dollar variances get worked first, and the automated
diagnostics give each item a starting hypothesis so browser time is spent confirming, not
guessing.

```bash
python3 scripts/triage_variances.py variances.txt --month "MM-YYYY" --out triage.json
```

The script prints the prioritized queue and writes `triage.json`. For each item it computes:

- **Estimated unit cost** (Cnt$/CntU, falling back to Pur$/PurU, then Beg$/BegU) and
  **variance dollars** (VarU × unit cost) — the priority key
- **Ledger tie-out**: does OnRecU = BegU + PurU + XfrU − SalU + AdjU? A failed tie means the
  ERP's own ledger is internally inconsistent — a posting problem, not a counting problem
- **Shrink plausibility**: |VarU| as a % of throughput, compared to the category's normal
  handling-loss threshold (fuels, grain)
- **UOM signature**: count-to-record ratios near ×2000 or ÷2000 (TON↔LB entry errors)
- **Sister-SKU offsets**: similar-description items with opposite-sign variances that roughly
  net to zero (product sold/received under the wrong SKU)
- **Adjustment flag**: AdjU ≠ 0 (a manual adjustment already touched this item this period)

Report the scope to Shawn before the loop starts: total items, total absolute variance
dollars, how many are above the materiality line, and estimated research time. Default
materiality: research every item ≥ $250 absolute variance individually; batch-disposition
smaller items using triage hints alone (note them in the workbook as "below materiality —
triage hint only"). Shawn can move this line.

### Step 3 — The research loop (one item at a time)

Read `references/root-causes.md` now if you haven't. Work the queue in priority order. For
each item, run the checks in this order and **stop as soon as the evidence supports a
confident root cause** — the sequence is ordered by diagnostic power per minute spent:

1. **Start from the triage hypothesis.** If triage flagged a failed ledger tie, UOM
   signature, or sister-SKU offset, verify that hypothesis first — it usually resolves the
   item in one or two page visits.
2. **Locate the variance.** The company-summary number can hide offsetting branch errors.
   Rerun the variance report for this item's category with Location set to each active branch
   (see intranet-pages.md), or use the report's per-location drill-down if available. An
   overage at one branch offsetting a shortage at another is the classic unposted-transfer
   signature.
3. **Check receiving timing.** Open the item's FIFO/purchase history
   (`itemFIFO.asp` — padded-key URL format in intranet-pages.md). Purchases dated just after
   the count date, or a delivered-but-unreceived BOL in the Procurement Document Center
   (`ProcurementDocumentCenter.asp`), explain an overage on the floor that the ERP hasn't
   booked yet.
4. **Check sales timing.** Sales activity right around the count date (fuel deliveries, grain
   tickets) posted after the count was taken explains a shortage that isn't real.
5. **Review adjustments.** If AdjU ≠ 0, find what the adjustment was for. A prior-period
   variance that was already adjusted, then counted again, double-dips. A fat-fingered
   adjustment shows up as a round-number AdjU that mirrors the variance.
6. **Check the physical story.** If nothing above explains it: is the variance consistent
   with normal shrink for the category (triage already computed this)? Is the item one of
   several near-identical SKUs (seed lots, chemical sizes) where a count sheet mix-up is
   likely? Then the disposition is "recount" or "accept as shrink," not more ERP archaeology.

**Record findings as you go.** After each item, append a record to `findings.json` (schema
below) — never hold findings only in memory; a session interruption should cost one item,
not the whole run. Report progress to Shawn every 10 items: items done, dollars explained,
top causes so far.

Findings record:
```json
{
  "sku": "9606595", "desc": "...", "category": "LIQ FERT", "uom": "LB",
  "var_units": -4000, "unit_cost": 0.1795, "var_dollars": -718.00,
  "checks": ["ledger tie OK", "per-branch: short 316, over 96", "FIFO reviewed"],
  "evidence": "Branch 96 shows +4,020 overage; transfer 96→316 dated 2/27 not posted at 316",
  "root_cause": "XFER-UNPOSTED",
  "confidence": "High",
  "action": "Post receiving side of transfer at branch 316, then re-verify count",
  "action_owner": "Booker bookkeeper",
  "status": "explained"
}
```

Use the root-cause codes from `references/root-causes.md` (TIMING-RECEIPT, TIMING-SALE,
XFER-UNPOSTED, UOM-ERROR, SISTER-SKU-MIX, ADJ-ERROR, LEDGER-INCONSISTENT, SHRINK-NORMAL,
COUNT-ERROR-SUSPECTED, DATA-ANOMALY, UNRESOLVED). Confidence is High only when a specific
transaction was located that accounts for the variance quantity (±10%); Medium when the
pattern matches but the specific transaction wasn't pinned down; Low for informed guesses.

**This skill researches and recommends — it does not post corrections.** Cost changes,
adjustment entries, and transfer postings are Shawn's (or the branch bookkeeper's) call; the
workbook is the handoff. The one exception: if Shawn explicitly asks to fix something during
the run, the Change Cost form workflow in the fifo-inventory-valuation skill applies.

### Step 4 — Build the research workbook

```bash
python3 scripts/build_research_workbook.py findings.json triage.json \
    --month "MM-YYYY" --out VarianceResearch_MMYYYY.xlsx
```

Four sheets (formatting conventions match the other Equity Exchange workbooks):

1. **Dashboard** — total variance $, explained vs unresolved counts and dollars, breakdown
   by root cause, breakdown by action owner
2. **Research Log** — every researched item: variance units/dollars, checks performed,
   evidence, root cause, confidence, recommended action. Sorted by |variance $| descending
3. **Action Items** — explained items grouped by corrective action type, with owner column —
   this is the sheet that gets forwarded to branches
4. **Unresolved & Recounts** — items needing a physical recount or manual review, red header

### Step 5 — Present the results

Share the workbook, then summarize in plain terms:
- Dollars explained vs. dollars still open
- The top 3 root causes by dollar impact ("$4,100 of the variance is unposted transfers
  between Spearman and Booker")
- Systemic patterns worth fixing upstream (e.g., the same branch repeatedly late posting
  BOLs — that's a process finding, not an item finding)
- The recount list, shortest path to closing the rest

## Error handling

- **Page load failure**: retry once; then mark the item's affected check as "PAGE ERROR" in
  its findings record and continue — don't stall the queue on one item.
- **Session timeout** (redirect to login): stop and tell Shawn immediately; findings.json
  preserves progress so the run resumes where it left off.
- **Item not found in drill-down pages**: record as DATA-ANOMALY with the symptom; these are
  often XREF/virtual-branch (999) artifacts.
- **Resuming a run**: if findings.json already has records for this month, skip those SKUs
  and continue the queue — say so, don't silently redo them.

## Branch reference

| Branch | Name | | Branch | Name |
|--------|------|-|--------|------|
| 26 | SEED WAREHOUSE | | 326 | TOWN AND COUNTRY |
| 56 | PRINGLE/MORSE | | 376 | DARROUZETT |
| 96 | SPEARMAN | | 386 | PETERSBURG |
| 316 | BOOKER | | 466 | EAST LOOP ROAD |
| 526 | EAKLY | | 999 | XREF / VIRTUAL |
