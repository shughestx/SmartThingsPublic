# Root-Cause Taxonomy for Count Variances

Every count variance (physical count ≠ on-record units) has a finite set of possible causes.
This file lists each cause, the signature that identifies it in the data, the evidence to
collect before claiming it, and the standard corrective action. Work top-down within an item:
the causes are roughly ordered from "cheap to confirm" to "expensive to confirm."

A variance is **positive (overage)** when CntU > OnRecU — more product on the floor than the
books say. **Negative (shortage)** when CntU < OnRecU.

---

## LEDGER-INCONSISTENT — the ERP's own math doesn't tie

- **Signature**: OnRecU ≠ BegU + PurU + XfrU − SalU + AdjU (triage computes this). The
  variance isn't count-vs-record; the record itself is broken.
- **Evidence**: the tie-out delta from triage; the specific column that looks wrong (e.g.,
  Beg balance doesn't match prior month's ending).
- **Action**: refer to ERP support / IT before anything else — researching transactions
  against a broken ledger wastes time. Note the delta in the workbook.
- **Typical confidence**: High (it's arithmetic).

## TIMING-RECEIPT — product arrived, ERP hasn't booked it yet

- **Signature**: overage; purchases or an open PO around the count date.
- **Where to look**: `itemFIFO.asp` purchase history — a receipt dated just AFTER the count
  date roughly matching the overage quantity. Procurement Document Center — a green-badge PO
  or BOL delivered before count date but not yet received in the ERP.
- **Evidence**: the specific PO/BOL number, delivery date vs. count date, quantity.
- **Action**: receive the BOL into the correct period (or note that the following period
  self-corrects); flag the branch if late posting is a habit.
- **Typical confidence**: High when a BOL matching the quantity (±10%) is found.

## TIMING-SALE — product left, sale not yet posted

- **Signature**: shortage; sales activity around the count date (DTF fuel deliveries and
  grain shipments are the usual suspects — product moves on tickets that get keyed later).
- **Evidence**: ticket/invoice dated on or just after count date matching the shortage.
- **Action**: none if the next period catches it; note it. If tickets routinely lag counts,
  that's a process finding for the branch.
- **Typical confidence**: High with a matching ticket; Medium from pattern alone.

## XFER-UNPOSTED — transfer posted on one side only

- **Signature**: at company level often invisible or small; per-branch view shows an overage
  at one branch and an offsetting shortage at another for the same item. XfrU ≠ 0, or a
  branch pair that historically ships to each other (96↔316, 56↔96).
- **Where to look**: per-branch variance report for the item; XfrU column by branch.
- **Evidence**: the two branch variances and how they net; the transfer date if findable.
- **Action**: post the missing side of the transfer at the identified branch; recount only
  if the net doesn't zero out.
- **Typical confidence**: High when the branch pair nets to ~zero.

## UOM-ERROR — quantity keyed in the wrong unit

- **Signature**: variance magnitude wildly disproportionate to the item's normal activity,
  with a telltale ratio: ×2000 or ÷2000 (TON keyed as LB or vice versa — LIQ FERT, DRY FERT,
  NH3 are the at-risk categories). Triage flags candidate ratios.
- **Evidence**: the specific transaction (purchase, transfer, or adjustment) whose quantity
  is off by the conversion factor.
- **Action**: reverse and re-key the transaction in the correct unit; the variance should
  then close without a count adjustment.
- **Typical confidence**: High when the ratio is within a few % of the factor.

## SISTER-SKU-MIX — right product, wrong item number

- **Signature**: two similar items (same product family, different size/lot/brand) with
  opposite-sign variances that roughly net to zero. Common in SEED (lots), AG CHEMICAL
  (jug vs. shuttle vs. bulk), and FEEDS. Triage detects candidate pairs by description.
- **Evidence**: the pair, their variances, and the net; ideally the mis-keyed sale/receipt.
- **Action**: post an item-to-item adjustment moving the quantity between the SKUs (net
  inventory value change should be ~zero if costs are close); remind counters/cashiers about
  the lookalike pair.
- **Typical confidence**: Medium-High from the netting pattern alone.

## ADJ-ERROR — an adjustment caused or doubled the variance

- **Signature**: AdjU ≠ 0 this period. Two failure modes: (a) a prior variance was adjusted
  AND the correction got counted again → doubled effect; (b) fat-fingered adjustment
  (round-number AdjU that mirrors VarU).
- **Evidence**: the adjustment entry — date, quantity, who/why if visible.
- **Action**: reverse the erroneous adjustment; do NOT post a new count adjustment on top of
  a bad one.
- **Typical confidence**: High when the adjustment quantity matches the variance.

## SHRINK-NORMAL — expected physical loss

- **Signature**: shortage that is a small fraction of throughput. Rule-of-thumb thresholds
  (|VarU| ÷ (PurU + SalU)): fuels ≤ 0.5% (evaporation/temperature), grain ≤ 0.25% (handling),
  dry/liquid fert ≤ 0.5% (spillage/heel), everything else ≤ 0.1%. Triage computes this.
- **Evidence**: the shrink percentage vs. threshold; no contradicting transaction evidence.
- **Action**: accept — post the count adjustment as shrink. If the same item runs above
  threshold multiple months, escalate (metering problem, or worse).
- **Typical confidence**: Medium (shrink is a diagnosis of exclusion — run checks 1–5 first
  for material dollars).

## COUNT-ERROR-SUSPECTED — the count itself is probably wrong

- **Signature**: none of the above fits; or the variance is implausible physically (e.g.,
  shortage exceeding what the tank/bin holds); or negative CntU.
- **Action**: recount before posting anything. List on the Unresolved & Recounts sheet with
  what to verify (location, unit, lookalike SKUs nearby).
- **Typical confidence**: n/a — this is a disposition, not an explanation.

## DATA-ANOMALY — the record itself is malformed

- **Signature**: negative counted quantity, zero-cost item distorting dollars, item living on
  the XREF/virtual branch (999), item missing from drill-down pages.
- **Action**: route to whoever maintains the item master; exclude from dollar totals if cost
  is bogus (note it).

## UNRESOLVED — researched, no cause found

Use sparingly and honestly. Record which checks were run so the next person doesn't repeat
them. An UNRESOLVED with a complete checks list is a legitimate outcome; an UNRESOLVED with
two checks is just an unfinished item.

---

## Claiming confidence

- **High** — a specific transaction/document was located that accounts for the variance
  quantity within ±10%.
- **Medium** — the pattern signature matches (netting pair, shrink ratio, ratio factor) but
  the individual transaction wasn't pinned down.
- **Low** — best available hypothesis; say what would confirm it.

Never let a plausible story substitute for the quantity check: an unposted BOL for 500 units
does not explain a 4,000-unit overage. If the quantities don't line up, keep the item open
and say what portion is explained.
