#!/usr/bin/env python3
"""Triage pass for inventory variance research — Equity Exchange.

Reads the pipe-delimited item lines extracted from the variance report
(Variance Only = ON, Company Summary) and produces a prioritized research
queue with automated diagnostic hints, so browser research time is spent
confirming hypotheses instead of forming them.

Input line format (one item per line):
  SKU|Desc|UOM|Cat|BegU|PurU|XfrU|SalU|AdjU|OnRecU|CntU|VarU|Beg$|Pur$|Xfr$|Rev$|Adj$|Cnt$|Margin$|MarginPct

Usage:
  python3 triage_variances.py variances.txt --month "03-2026" --out triage.json
  python3 triage_variances.py variances.txt --materiality 250
"""
import argparse
import json
import re
import sys
from itertools import combinations

FIELDS = ["sku", "desc", "uom", "cat", "beg_u", "pur_u", "xfr_u", "sal_u",
          "adj_u", "onrec_u", "cnt_u", "var_u", "beg_d", "pur_d", "xfr_d",
          "rev_d", "adj_d", "cnt_d", "margin_d", "margin_pct"]
NUMERIC = FIELDS[4:]

# |VarU| / throughput above which a shortage stops looking like normal shrink
SHRINK_THRESHOLDS = {
    "CLEAR DIESEL": 0.005, "DYED DIESEL": 0.005, "FUEL NL": 0.005,
    "FUEL SNL": 0.005, "FUEL LP": 0.005,
    "MILO": 0.0025, "CORN": 0.0025, "WHEAT": 0.0025,
    "LIQ FERT": 0.005, "DRY FERT": 0.005, "NH3": 0.005,
}
DEFAULT_SHRINK_THRESHOLD = 0.001
UOM_FACTORS = (2000.0, 1 / 2000.0)  # TON <-> LB keying errors
STOPWORDS = {"THE", "AND", "OF", "PER", "W/", "WITH"}


def parse_num(s):
    s = (s or "").strip()
    neg = s.startswith("(") and s.endswith(")")
    s = re.sub(r"[$,%()\s]", "", s)
    try:
        v = float(s)
    except ValueError:
        v = 0.0
    return -v if neg else v


def parse_line(line):
    parts = line.rstrip("\n").split("|")
    if len(parts) < len(FIELDS):
        return None
    item = dict(zip(FIELDS, parts[:len(FIELDS)]))
    for f in NUMERIC:
        item[f] = parse_num(item[f])
    for f in ("sku", "desc", "uom", "cat"):
        item[f] = item[f].strip()
    return item


def unit_cost(item):
    """Best available cost per unit, with fallbacks; 0.0 means no usable cost."""
    for qty_f, dol_f in (("cnt_u", "cnt_d"), ("pur_u", "pur_d"), ("beg_u", "beg_d")):
        if abs(item[qty_f]) > 1e-9 and abs(item[dol_f]) > 1e-9:
            return abs(item[dol_f] / item[qty_f])
    return 0.0


def desc_tokens(desc):
    return frozenset(t for t in re.split(r"[^A-Z0-9]+", desc.upper())
                     if len(t) > 2 and t not in STOPWORDS)


def diagnose(item):
    """Return (hints, hypothesis) for a single item, ignoring cross-item patterns."""
    hints = []
    hypothesis = None

    # Ledger tie-out: OnRec should equal Beg + Pur + Xfr - Sal + Adj
    expected = (item["beg_u"] + item["pur_u"] + item["xfr_u"]
                - item["sal_u"] + item["adj_u"])
    tie_delta = item["onrec_u"] - expected
    item["ledger_tie_delta"] = round(tie_delta, 2)
    if abs(tie_delta) > 0.01 * max(1.0, abs(item["onrec_u"])):
        hints.append(f"LEDGER TIE FAILS by {tie_delta:+,.1f} units")
        hypothesis = "LEDGER-INCONSISTENT"

    # UOM signature: counted vs on-record ratio near a conversion factor
    if abs(item["onrec_u"]) > 1e-9 and abs(item["cnt_u"]) > 1e-9:
        ratio = abs(item["cnt_u"] / item["onrec_u"])
        for factor in UOM_FACTORS:
            if 0.95 <= ratio / factor <= 1.05:
                hints.append(f"UOM signature: count/record ratio ~ {factor:g}")
                hypothesis = hypothesis or "UOM-ERROR"

    # Shrink plausibility (shortages only)
    throughput = abs(item["pur_u"]) + abs(item["sal_u"])
    if item["var_u"] < 0 and throughput > 0:
        pct = abs(item["var_u"]) / throughput
        item["shrink_pct"] = round(pct, 5)
        threshold = SHRINK_THRESHOLDS.get(item["cat"].upper(), DEFAULT_SHRINK_THRESHOLD)
        if pct <= threshold:
            hints.append(f"shrink-plausible: {pct:.2%} of throughput "
                         f"(threshold {threshold:.2%})")
            hypothesis = hypothesis or "SHRINK-NORMAL"

    # Prior adjustment touched this item
    if abs(item["adj_u"]) > 1e-9:
        hints.append(f"AdjU = {item['adj_u']:+,.1f} this period — review the adjustment")
        if abs(abs(item["adj_u"]) - abs(item["var_u"])) <= 0.1 * max(1.0, abs(item["var_u"])):
            hints.append("adjustment magnitude ~= variance — possible ADJ-ERROR/double-dip")
            hypothesis = hypothesis or "ADJ-ERROR"

    # Transfers in play
    if abs(item["xfr_u"]) > 1e-9:
        hints.append(f"XfrU = {item['xfr_u']:+,.1f} — check per-branch for unposted side")
        hypothesis = hypothesis or "XFER-UNPOSTED?"

    # Data anomalies
    if item["cnt_u"] < 0:
        hints.append("negative counted quantity — DATA-ANOMALY")
        hypothesis = "DATA-ANOMALY"
    return hints, hypothesis


def find_sister_offsets(items):
    """Flag pairs of similar-description items whose variances roughly net to zero."""
    candidates = [it for it in items if abs(it["var_u"]) > 1e-9]
    for a, b in combinations(candidates, 2):
        if a["var_u"] * b["var_u"] >= 0:  # need opposite signs
            continue
        ta, tb = desc_tokens(a["desc"]), desc_tokens(b["desc"])
        if not ta or not tb:
            continue
        overlap = len(ta & tb) / min(len(ta), len(tb))
        if overlap < 0.6:
            continue
        net = a["var_u"] + b["var_u"]
        scale = max(abs(a["var_u"]), abs(b["var_u"]))
        if abs(net) <= 0.25 * scale:
            note = (f"sister-SKU offset candidate with {b['sku']} ({b['desc']}): "
                    f"{a['var_u']:+,.1f} vs {b['var_u']:+,.1f}, net {net:+,.1f}")
            a["hints"].append(note)
            b["hints"].append(f"sister-SKU offset candidate with {a['sku']} "
                              f"({a['desc']}): {b['var_u']:+,.1f} vs "
                              f"{a['var_u']:+,.1f}, net {net:+,.1f}")
            for it in (a, b):
                if not it["hypothesis"] or it["hypothesis"].endswith("?"):
                    it["hypothesis"] = "SISTER-SKU-MIX?"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", help="variances.txt with pipe-delimited item lines")
    ap.add_argument("--month", default="", help="reporting period MM-YYYY, for the output")
    ap.add_argument("--materiality", type=float, default=250.0,
                    help="research individually at/above this absolute variance $ (default 250)")
    ap.add_argument("--out", default="triage.json")
    args = ap.parse_args()

    items, skipped = [], 0
    with open(args.input) as fh:
        for line in fh:
            if not line.strip():
                continue
            item = parse_line(line)
            if item is None:
                skipped += 1
                continue
            items.append(item)
    if skipped:
        print(f"WARNING: skipped {skipped} malformed line(s)", file=sys.stderr)

    for it in items:
        it["unit_cost"] = round(unit_cost(it), 4)
        it["var_dollars"] = round(it["var_u"] * it["unit_cost"], 2)
        it["hints"], it["hypothesis"] = diagnose(it)
        if it["unit_cost"] == 0.0 and abs(it["var_u"]) > 1e-9:
            it["hints"].append("no usable cost — variance $ understated; check FIFO cost")

    find_sister_offsets(items)

    queue = sorted((it for it in items if abs(it["var_u"]) > 1e-9),
                   key=lambda it: abs(it["var_dollars"]), reverse=True)
    material = [it for it in queue if abs(it["var_dollars"]) >= args.materiality]
    below = [it for it in queue if abs(it["var_dollars"]) < args.materiality]
    total_abs = sum(abs(it["var_dollars"]) for it in queue)

    out = {
        "month": args.month,
        "materiality": args.materiality,
        "total_items_with_variance": len(queue),
        "total_abs_variance_dollars": round(total_abs, 2),
        "material_items": len(material),
        "below_materiality_items": len(below),
        "queue": queue,
    }
    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=2)

    print(f"Variance triage — {args.month or 'period not specified'}")
    print(f"  Items with unit variances : {len(queue)}")
    print(f"  Total |variance $|        : ${total_abs:,.2f}")
    print(f"  Material (>= ${args.materiality:,.0f})     : {len(material)}"
          f"  |  below line: {len(below)}")
    print(f"  Written to                : {args.out}\n")
    print(f"{'#':>3} {'SKU':<10} {'Description':<32} {'VarU':>10} {'Var $':>11}  Hypothesis / hints")
    for i, it in enumerate(material, 1):
        hyp = it["hypothesis"] or "-"
        first_hint = it["hints"][0] if it["hints"] else ""
        print(f"{i:>3} {it['sku']:<10} {it['desc'][:32]:<32} "
              f"{it['var_u']:>10,.1f} {it['var_dollars']:>11,.2f}  {hyp}"
              f"{' — ' + first_hint if first_hint else ''}")
    if below:
        print(f"\n({len(below)} items below the ${args.materiality:,.0f} materiality line — "
              "disposition from triage hints, no individual research)")


if __name__ == "__main__":
    main()
