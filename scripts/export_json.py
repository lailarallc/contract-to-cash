"""Export Contract-to-Cash data to static JSON for the React SPA.

Queries the Cinderhaven Data Platform and produces:
  - summary.json:    headline numbers, total gross-to-net
  - lifecycle.json:  waterfall stages (deduction type breakdown)
  - retailers.json:  per-retailer leakage comparison + time-to-cash

Usage:
    DATABASE_URL=postgresql://... python scripts/export_json.py
"""

from __future__ import annotations

import json
from pathlib import Path

from db import connect

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "frontend" / "public" / "json"

# Public surfaces show a role label for each trade partner, never the real
# name (reference/retailer_display_labels.json, vendored from the canon repo).
# The database keeps the real names; the label is applied here, on export.
_LABELS = json.loads((ROOT / "reference" / "retailer_display_labels.json").read_text(encoding="utf-8"))
PUBLIC_NAME = {
    entry["name"]: entry["label"][0].upper() + entry["label"][1:]
    for group in ("retailers", "distributors")
    for entry in _LABELS[group].values()
}


def public_name(name: str) -> str:
    """Role label for a dataset partner name; unknown names pass through."""
    return PUBLIC_NAME.get(name, name)


# One window for every part (owner, 2026-11-17): CY2023-2025, the canon's trailing_36m. B2B on remittances
# received in the window; DTC on the orders placed in it, with each order's fees, refunds and lost
# chargebacks whenever they fell. The headline figures are the canon keys; the export recomputes each and
# stops if the database and the canon disagree (check_against_canon), so the page never prints a hand-edit.
PERIOD_START = "2023-01-01"
PERIOD_END = "2025-12-31"
PERIOD_LABEL = "Jan 2023 – Dec 2025"

CANON = json.loads((ROOT / "reference" / "canonical_values.json").read_text(encoding="utf-8"))
CANON_KEYS = {
    # export figure -> canon key (trailing_36m = CY2023-2025)
    "b2b.gross_payments": "revenue.gross_payments_retailer.trailing_36m",
    "b2b.net_received": "revenue.net_collected_retailer.trailing_36m",
    "dtc.gross": "revenue.dtc_gross.trailing_36m",
    "dtc.processing_fees": "revenue.dtc_processing_fees.trailing_36m",
    "dtc.refunds": "revenue.dtc_refunds.trailing_36m",
    "dtc.chargebacks_lost": "revenue.dtc_chargebacks_lost.trailing_36m",
    "dtc.net_received": "revenue.dtc_net.trailing_36m",
    "combined.total_invoiced": "lifecycle.retailer_dtc_gross.trailing_36m",
    "combined.total_net": "lifecycle.retailer_dtc_net.trailing_36m",
    "combined.cents_per_dollar": "lifecycle.retailer_dtc_cents_per_dollar.trailing_36m",
}


def canon(key: str) -> float:
    node = CANON
    for part in key.split("."):
        node = node[part]
    return float(node)


def check_against_canon(summary: dict) -> None:
    """Every keyed figure equals its canon key at the key's precision; otherwise the export stops."""
    bad = []
    for path, key in CANON_KEYS.items():
        section, field = path.split(".")
        got, want = summary[section][field], canon(key)
        places = 1 if field == "cents_per_dollar" else 2  # the page prints cents to one place
        if round(got, places) != round(want, places):
            bad.append(f"{path} = {got} but canon {key} = {want}")
    if bad:
        raise SystemExit("export disagrees with the canon:\n  " + "\n  ".join(bad))

ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
        "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
        "Seventeen", "Eighteen", "Nineteen"]
TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def num_to_word(n: int) -> str:
    if n == 0:
        return "Zero"
    if n < 20:
        return ONES[n]
    if n >= 100:
        return str(n)
    return f"{TENS[n // 10]}-{ONES[n % 10]}" if n % 10 else TENS[n // 10]


def write_json(filename, data, indent=2):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, default=str)
    print(f"  Wrote {path.relative_to(ROOT)} ({path.stat().st_size:,} bytes)", flush=True)


def export_summary(cur):
    """Top-line metrics for the hero section."""
    print("\n--- summary.json ---", flush=True)

    # B2B payments (retailers only, within period).
    cur.execute("""
        SELECT
            SUM(p.gross_amount) AS b2b_gross,
            SUM(p.net_amount) AS b2b_net,
            COUNT(*) AS remittance_count
        FROM fct_retailer_payments p
        WHERE p.received_date BETWEEN %s AND %s
    """, (PERIOD_START, PERIOD_END))
    pay = cur.fetchone()

    # B2B invoiced (retailers only, within period).
    cur.execute("""
        SELECT SUM(o.total_value) AS total, COUNT(DISTINCT o.order_id) AS order_count
        FROM fct_retailer_orders o
        WHERE o.po_date BETWEEN %s AND %s
    """, (PERIOD_START, PERIOD_END))
    orders_row = cur.fetchone()
    b2b_invoiced = orders_row["total"]
    b2b_order_count = orders_row["order_count"]

    # B2B deductions (retailers only, within period via payment date).
    cur.execute("""
        SELECT COUNT(*) AS n, SUM(d.deduction_amount) AS total,
               SUM(d.recovered_amount) AS recovered
        FROM fct_retailer_deductions d
        JOIN fct_retailer_payments p ON p.remittance_id = d.remittance_id
        WHERE p.received_date BETWEEN %s AND %s
    """, (PERIOD_START, PERIOD_END))
    ded = cur.fetchone()

    # Retailer count.
    cur.execute("""
        SELECT COUNT(*) AS n FROM dim_retailers
    """)
    retailer_count = cur.fetchone()["n"]

    # DTC: the orders placed in the window, and each one's fees, refunds and lost chargebacks.
    dtc = dtc_cohort(cur)
    dtc_txn = {"fees": dtc["fees"]}
    dtc_refunds = dtc["refunds"]
    dtc_cb = dtc["chargebacks"]
    dtc_leakage = dtc["fees"] + dtc_refunds + dtc_cb
    dtc_gross = dtc["gross"]
    dtc_net = dtc_gross - dtc_leakage

    # DTC order count in period.
    cur.execute("""
        SELECT COUNT(DISTINCT order_id) AS n FROM fct_dtc_orders
        WHERE created_at::date BETWEEN %s AND %s
    """, (PERIOD_START, PERIOD_END))
    dtc_order_count = cur.fetchone()["n"]

    # Combined, on one basis: B2B gross on the remittances received in the window (the invoice amounts
    # they settle), not orders placed in it, so gross and net count the same remittances.
    combined_invoiced = pay["b2b_gross"] + dtc_gross
    combined_net = pay["b2b_net"] + dtc_net
    combined_leakage = (pay["b2b_gross"] - pay["b2b_net"]) + dtc_leakage

    headline_ratio = combined_net / combined_invoiced if combined_invoiced else 0
    cents = round(combined_net / combined_invoiced * 100, 1)
    cents_word = num_to_word(int(cents))
    headline = f"For Every Dollar Invoiced, {cents_word} Cents Arrives as Cash"

    summary = {
        "headline": headline,
        "headline_ratio": round(headline_ratio, 3),
        "b2b": {
            "invoiced": round(b2b_invoiced, 2),
            "gross_payments": round(pay["b2b_gross"], 2),
            "net_received": round(pay["b2b_net"], 2),
            "total_deductions": round(ded["total"], 2),
            "deduction_count": ded["n"],
            "recovered": round(ded["recovered"], 2),
            "leakage_pct": round((pay["b2b_gross"] - pay["b2b_net"]) / pay["b2b_gross"] * 100, 1) if pay["b2b_gross"] else 0,
            "remittance_count": pay["remittance_count"],
        },
        "dtc": {
            "gross": round(dtc_gross, 2),
            "processing_fees": round(dtc_txn["fees"] or 0, 2),
            "refunds": round(dtc_refunds, 2),
            "chargebacks_lost": round(dtc_cb, 2),
            "net_received": round(dtc_net, 2),
            "leakage_pct": round(dtc_leakage / dtc_gross * 100, 1) if dtc_gross else 0,
        },
        "combined": {
            "total_invoiced": round(combined_invoiced, 2),
            "total_net": round(combined_net, 2),
            "total_leakage": round(combined_leakage, 2),
            "cents_per_dollar": cents,
        },
        "meta": {
            # No flattened counterparty count: canonical phrasing is
            # "6 retail partners + DTC", never a combined "7" (DTC is not a retailer).
            "retailers_b2b": retailer_count,
            "orders_b2b": b2b_order_count,
            "orders_dtc": dtc_order_count,
            "skus": 50,  # Cinderhaven product catalog size (canonical: seed_config.py)
            "time_window": PERIOD_LABEL,
        },
    }

    check_against_canon(summary)
    write_json("summary.json", summary)
    return summary


def dtc_cohort(cur) -> dict:
    """DTC orders placed in the window (revenue.dtc_gross's cohort) and each order's leakage, whenever it fell."""
    cur.execute("""
        WITH o AS (
            SELECT order_id, total FROM raw.shopify_orders
            WHERE created_at::date BETWEEN %s AND %s
        )
        SELECT
            (SELECT SUM(total) FROM o) AS gross,
            (SELECT SUM(t.processing_fee) FROM raw.shopify_transactions t JOIN o USING (order_id)) AS fees,
            (SELECT SUM(r.refund_amount) FROM raw.shopify_refunds r JOIN o USING (order_id)) AS refunds,
            (SELECT SUM(c.chargeback_amount) FROM raw.shopify_chargebacks c JOIN o USING (order_id)
              WHERE c.outcome = 'lost') AS chargebacks
    """, (PERIOD_START, PERIOD_END))
    return {k: (v or 0) for k, v in cur.fetchone().items()}


def export_lifecycle(cur):
    """Waterfall stages — deduction type breakdown for the anchor chart."""
    print("\n--- lifecycle.json ---", flush=True)

    # B2B waterfall: gross → each deduction type → net (retailers only, within period).
    cur.execute("""
        SELECT SUM(p.gross_amount) AS gross
        FROM fct_retailer_payments p
        WHERE p.received_date BETWEEN %s AND %s
    """, (PERIOD_START, PERIOD_END))
    b2b_gross = cur.fetchone()["gross"]

    cur.execute("""
        SELECT d.deduction_type, COUNT(*) AS count,
               SUM(d.deduction_amount) AS amount,
               SUM(d.recovered_amount) AS recovered
        FROM fct_retailer_deductions d
        JOIN fct_retailer_payments p ON p.remittance_id = d.remittance_id
        WHERE p.received_date BETWEEN %s AND %s
        GROUP BY d.deduction_type
        ORDER BY SUM(d.deduction_amount) DESC
    """, (PERIOD_START, PERIOD_END))
    deduction_stages = []
    for row in cur.fetchall():
        deduction_stages.append({
            "stage": row["deduction_type"],
            "label": row["deduction_type"].replace("_", " ").title(),
            "amount": round(row["amount"], 2),
            "count": row["count"],
            "recovered": round(row["recovered"] or 0, 2),
        })

    cur.execute("""
        SELECT SUM(p.net_amount) AS net
        FROM fct_retailer_payments p
        WHERE p.received_date BETWEEN %s AND %s
    """, (PERIOD_START, PERIOD_END))
    b2b_net = cur.fetchone()["net"]

    categorized = sum(s["amount"] for s in deduction_stages)
    unclassified = round(b2b_gross - b2b_net - categorized, 2)
    if unclassified > 0:
        # The gross-to-net residual is NOT an itemized deduction: it carries no
        # deduction record (count == 0), so it is reported separately and never
        # counted as trade "deductions." It keeps the waterfall footing to
        # gross - net without mislabeling un-itemized trade spend as a deduction.
        deduction_stages.append({
            "stage": "unreconciled",
            "label": "Unreconciled / trade spend not itemized",
            "amount": unclassified,
            "count": 0,
            "recovered": 0,
        })

    # DTC waterfall: the same order cohort as summary.json.
    dtc = dtc_cohort(cur)
    dtc_gross = dtc["gross"]
    dtc_fees = dtc["fees"]
    dtc_refunds = dtc["refunds"]
    dtc_chargebacks = dtc["chargebacks"]

    dtc_net = dtc_gross - dtc_fees - dtc_refunds - dtc_chargebacks

    lifecycle = {
        "b2b": {
            "gross": round(b2b_gross, 2),
            "net": round(b2b_net, 2),
            "stages": deduction_stages,
        },
        "dtc": {
            "gross": round(dtc_gross, 2),
            "net": round(dtc_net, 2),
            "stages": [
                {"stage": "processing_fees", "label": "Processing Fees", "amount": round(dtc_fees, 2)},
                {"stage": "refunds", "label": "Refunds", "amount": round(dtc_refunds, 2)},
                {"stage": "chargebacks", "label": "Chargebacks", "amount": round(dtc_chargebacks, 2)},
            ],
        },
    }

    write_json("lifecycle.json", lifecycle)
    return lifecycle


def export_retailers(cur):
    """Per-retailer leakage comparison and time-to-cash."""
    print("\n--- retailers.json ---", flush=True)

    # Leakage by retailer (within period).
    cur.execute("""
        SELECT
            dr.retailer_name,
            SUM(p.gross_amount) AS gross,
            SUM(p.net_amount) AS net,
            SUM(p.gross_amount) - SUM(p.net_amount) AS leakage,
            COUNT(*) AS remittance_count
        FROM fct_retailer_payments p
        JOIN dim_retailers dr ON dr.retailer_id = p.retailer_id
        WHERE p.received_date BETWEEN %s AND %s
        GROUP BY dr.retailer_name
        ORDER BY SUM(p.gross_amount) - SUM(p.net_amount) DESC
    """, (PERIOD_START, PERIOD_END))
    retailer_leakage = []
    for row in cur.fetchall():
        leak_pct = row["leakage"] / row["gross"] * 100 if row["gross"] else 0
        retailer_leakage.append({
            "name": public_name(row["retailer_name"]),
            "gross": round(row["gross"], 2),
            "net": round(row["net"], 2),
            "leakage": round(row["leakage"], 2),
            "leakage_pct": round(leak_pct, 1),
            "remittances": row["remittance_count"],
        })

    # Time-to-cash by retailer — ONE ROW PER ORDER (deduped), not one row per
    # deduction, so the average is not weighted by how many deductions an order
    # drew. Anchored on po_date, which every retailer records (810 invoice dates
    # are Walmart-only, so invoice date is not usable across retailers). Payments
    # carry no order_id, so a deduction is the only bridge from an order to a
    # payment — this can therefore only be measured for orders that have a
    # recorded, deduction-linked payment. days_to_cash = po_date to first payment.
    cur.execute("""
        WITH order_payment AS (
            SELECT
                dr.retailer_name,
                o.order_id,
                MIN(p.received_date - o.po_date) AS days_to_cash
            FROM fct_retailer_deductions d
            JOIN fct_retailer_orders o ON o.order_id = d.order_id
            JOIN fct_retailer_payments p ON p.remittance_id = d.remittance_id
            JOIN dim_retailers dr ON dr.retailer_id = d.retailer_id
            WHERE o.po_date BETWEEN %s AND %s
            GROUP BY dr.retailer_name, o.order_id
        )
        SELECT
            retailer_name,
            COUNT(*) AS sample_size,
            ROUND(AVG(days_to_cash), 1) AS avg_days,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY days_to_cash) AS median_days
        FROM order_payment
        GROUP BY retailer_name
        ORDER BY AVG(days_to_cash) DESC
    """, (PERIOD_START, PERIOD_END))
    time_to_cash = []
    for row in cur.fetchall():
        time_to_cash.append({
            "name": public_name(row["retailer_name"]),
            "avg_days": float(row["avg_days"]),
            "median_days": float(row["median_days"]),
            "sample_size": row["sample_size"],
        })

    # Coverage: time-to-cash can only be measured for orders that have a linked
    # payment. Disclose that share honestly instead of implying full coverage.
    covered_orders = sum(r["sample_size"] for r in time_to_cash)
    cur.execute("""
        SELECT COUNT(DISTINCT order_id) AS n
        FROM fct_retailer_orders
        WHERE po_date BETWEEN %s AND %s
    """, (PERIOD_START, PERIOD_END))
    total_orders = cur.fetchone()["n"]
    coverage_pct = round(covered_orders / total_orders * 100, 1) if total_orders else 0

    # Top deduction types per retailer (within period).
    cur.execute("""
        SELECT
            dr.retailer_name,
            d.deduction_type,
            SUM(d.deduction_amount) AS amount,
            COUNT(*) AS count
        FROM fct_retailer_deductions d
        JOIN dim_retailers dr ON dr.retailer_id = d.retailer_id
        JOIN fct_retailer_payments p ON p.remittance_id = d.remittance_id
        WHERE p.received_date BETWEEN %s AND %s
        GROUP BY dr.retailer_name, d.deduction_type
        ORDER BY dr.retailer_name, SUM(d.deduction_amount) DESC
    """, (PERIOD_START, PERIOD_END))
    deduction_mix = {}
    for row in cur.fetchall():
        name = public_name(row["retailer_name"])
        if name not in deduction_mix:
            deduction_mix[name] = []
        deduction_mix[name].append({
            "type": row["deduction_type"],
            "label": row["deduction_type"].replace("_", " ").title(),
            "amount": round(row["amount"], 2),
            "count": row["count"],
        })

    retailers = {
        "leakage": retailer_leakage,
        "time_to_cash": time_to_cash,
        "time_to_cash_meta": {
            "covered_orders": covered_orders,
            "total_orders": total_orders,
            "coverage_pct": coverage_pct,
        },
        "deduction_mix": deduction_mix,
    }

    write_json("retailers.json", retailers)
    return retailers


def main():
    print("=" * 60, flush=True)
    print("  CONTRACT-TO-CASH: JSON EXPORT")
    print("=" * 60, flush=True)

    conn = connect()
    try:
        cur = conn.cursor()

        summary = export_summary(cur)
        lifecycle = export_lifecycle(cur)
        retailers = export_retailers(cur)

        print(f"\n{'=' * 60}")
        print(f"  Export complete. Files in frontend/public/json/")
        print(f"  Headline ratio: {summary['combined']['cents_per_dollar']}c per dollar")
        print(f"{'=' * 60}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
