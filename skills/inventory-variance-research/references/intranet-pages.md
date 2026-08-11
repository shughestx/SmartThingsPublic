# Intranet Page Catalog for Variance Research

All pages live under `https://secure.perrytonequity.com/intranet/`. Shawn's browser session
is already authenticated; a redirect to a login page means the session expired — stop and
tell him.

## Variance report — the source list

```
/inventory/menuvariancereport.asp
```
Parameters: Report Date `MM-YYYY`, Start Date / End Date (first/last of month), Location,
Variance Only checkbox, Select Period = Year To Date, Report Type = Normal.

- **Location = Company Summary** → one entry per item, company-wide, 12 columns per row,
  4 rows per item (units / dollars / rates / spacer). This is the triage input.
- **Location = a specific branch** → same structure scoped to that branch. Rerunning the
  report per branch is how a company-level variance gets localized (step 2 of the research
  loop). Branches: 26, 56, 96, 316, 326, 376, 386, 466, 526 (999 is XREF/virtual).
- Extraction: use the variance-margin-report skill's `extract_items.js` (two-phase:
  populate `window._varItems`, then read in slices of 10 to dodge the ~5000-char console
  output cap).
- Column semantics reminder: the report's "Variance $" column is actually gross margin $,
  NOT a dollarized count variance. Dollarize variances yourself (VarU × unit cost) — the
  triage script does this.

## Item FIFO / purchase history — receiving evidence

```
/inventory/itemFIFO.asp?item_key={KEY}&count_key={QTY}&inv_date={M/DD/YYYY}&fin_date={MM-YYYY}
```

- `{KEY}` is the item number **left-padded with spaces to 16 characters total**, URL-encoded
  (`%20` per space). A 7-digit item gets 9 leading spaces:
  `item_key=%20%20%20%20%20%20%20%20%209606595`
- Shows purchase records with vendor and date — this is where receipt-timing evidence lives.
  Compare purchase dates to the count date.
- "FIFO Product Cost Per Unit" + "Addon Cost Per Unit" give a defensible unit cost for
  dollarizing a variance when the report-derived cost looks off. **Unit caution**: for
  LIQ FERT / DRY FERT / NH3 the FIFO cost is per TON while inventory tracks LB — divide by
  2,000 before using it against LB quantities.
- No purchase records at all → the page shows only the branch table; note "no FIFO data."

## Inventory summary — current position by item

```
/inventory/InventorySummary.asp
```
All items, sorted descending by value, single huge page — extract via JavaScript
(`document.body.innerText`), not `read_page` (it will time out). Columns:
Count | Item | Description | Unit | Cost | Amount | Group | Sub-Group. Item numbers are
hyperlinked — the href reveals the item drill-down page, useful for finding an item's
transaction-level detail if a dedicated activity page exists. Follow one link and note the
URL pattern the first time; reuse it directly after that.

## Procurement Document Center — unposted BOL evidence

```
/purchaseorder/ProcurementDocumentCenter.asp
```
Shows POs with attached delivery documents. A PO with a delivered BOL that has not been
received into the ERP (green-badge status — see the po-receiving skill for the full reading
guide) is the classic TIMING-RECEIPT evidence. Search/filter by vendor or item where the
page allows.

## Document intake — recent scanned BOLs

```
/document/documentintake.asp
```
Recently uploaded delivery documents that may not yet be attached to POs. Secondary evidence
source when the Document Center shows nothing but an overage insists product arrived.

## Zero-value list — cost sanity check

```
/inventory/inventoryValueZero.asp?type=zero
```
Items counted but carrying $0.0000 cost. A variance item appearing here means its dollarized
variance is understated (cost is bogus) — flag DATA-ANOMALY on the dollars and use the FIFO
cost instead.

## Change Cost form — reference only

```
/inventory/company_inv_adj.asp?key=01&key2={MM-YYYY}&Key3={ITEM}&ProductCost=${COST}
```
This skill does not submit corrections, but the form's Prev Cost column (per branch) is a
quick way to read an item's book cost per branch without parsing InventorySummary.

## General navigation notes

- Give slow ASP pages up to ~10 seconds; retry once on failure, then record "PAGE ERROR"
  for that check and move on.
- Big report pages: extract with JavaScript DOM access; paginated views don't exist — pages
  render everything at once.
- Number parsing: negatives render as `(1,234.56)`; strip `$ , % ( )` and apply the sign.
