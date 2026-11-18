"""Cross-project reconciliation validation for Contract-to-Cash.

Verifies that C2C's view of the warehouse matches the platform's canon
(reference/canonical_values.json, vendored by scripts/refresh_canonical.py).
Every expected value is a canon key, read at run time; none is typed here.
Exits 0 on success, 1 on any mismatch.

Restated 2026-11-17 (Cinderhaven spec DECISIONS#u19-start): the previous
literals (5,838 orders, $31,409,072.52, 1,410 disputes, $98,215.54, 10,000 DTC
orders, $1,537,390.70) came from a retired schema, and the queries named
columns the marts no longer have (channel, line_total, was_disputed,
net_recovery, chargeback_fee).

Usage:
    DATABASE_URL=postgresql://... python scripts/validate_cross_project.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from db import connect

ROOT = Path(__file__).resolve().parent.parent
CANON = json.loads((ROOT / "reference" / "canonical_values.json").read_text(encoding="utf-8"))


def canon(key: str):
    node = CANON
    for part in key.split("."):
        node = node[part]
    return node


def main():
    checks = []
    failures = []

    def check(name, key, actual, places=None):
        """Actual equals the canon key exactly (counts) or at `places` decimals (money, rates)."""
        expected = canon(key)
        if places is None:
            passed = actual == expected
        else:
            passed = round(float(actual), places) == round(float(expected), places)
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}  ({key})")
        if not passed:
            print(f"         Canon:  {expected}")
            print(f"         Actual: {actual}")
            failures.append((name, expected, actual))
        checks.append((name, passed))

    print("=" * 60, flush=True)
    print("  CROSS-PROJECT RECONCILIATION VALIDATION (against the canon)")
    print("=" * 60)

    conn = connect()
    cur = conn.cursor()

    print("\n--- Retailer deductions ---\n", flush=True)
    cur.execute("""
        SELECT COUNT(*) AS n, SUM(deduction_amount) AS total, SUM(recovered_amount) AS recovered,
               COUNT(DISTINCT deduction_type) AS types
        FROM fct_retailer_deductions
    """)
    ded = cur.fetchone()
    check("Deduction count", "rows.retailer_deductions.all_time", ded["n"])
    check("Deduction total ($)", "deductions.retailer_total.all_time", ded["total"], places=2)
    check("Deduction types", "deductions.retailer_types.all_time", ded["types"])
    check("Recovered / deducted", "deductions_recovery.retailer_recovery_rate.all_time",
          ded["recovered"] / ded["total"], places=4)

    cur.execute("SELECT COUNT(*) AS n FROM raw.retailer_disputes")
    check("Disputes filed", "rows.retailer_disputes.all_time", cur.fetchone()["n"])

    print("\n--- Orders and shipments ---\n", flush=True)
    cur.execute("SELECT COUNT(DISTINCT order_id) AS n, SUM(total_value) AS total FROM fct_retailer_orders")
    orders = cur.fetchone()
    check("Retailer order count", "rows.retailer_orders.all_time", orders["n"])
    check("Retailer invoiced total ($)", "revenue_invoiced.gross_invoiced_retailer.all_time", orders["total"], places=2)
    cur.execute("SELECT COUNT(DISTINCT order_id) AS n FROM fct_dtc_orders")
    check("DTC order count", "rows.shopify_orders.all_time", cur.fetchone()["n"])
    cur.execute("SELECT COUNT(*) AS n FROM fct_retailer_shipments")
    check("Shipment count", "fulfillment.shipments.all_retailers_full_corpus", cur.fetchone()["n"])

    print("\n--- Retailers ---\n", flush=True)
    cur.execute("SELECT COUNT(*) AS n FROM dim_retailers")
    check("Retail partners", "universe.retailers.all_time", cur.fetchone()["n"])

    print("\n--- Payments: the page's window, CY2023-2025 ---\n", flush=True)
    cur.execute("""
        SELECT SUM(gross_amount) AS gross, SUM(net_amount) AS net FROM fct_retailer_payments
        WHERE received_date BETWEEN '2023-01-01' AND '2025-12-31'
    """)
    pay = cur.fetchone()
    check("Retailer remittances gross ($)", "revenue.gross_payments_retailer.trailing_36m", pay["gross"], places=2)
    check("Retailer remittances net ($)", "revenue.net_collected_retailer.trailing_36m", pay["net"], places=2)

    print("\n" + "=" * 60)
    total = len(checks)
    failed = len(failures)
    conn.close()
    if failed == 0:
        print(f"  ALL {total} CHECKS PASSED")
        print("=" * 60)
        sys.exit(0)
    print(f"  {failed} of {total} CHECKS FAILED:")
    for name, expected, actual in failures:
        print(f"    - {name}: canon {expected}, got {actual}")
    print("=" * 60)
    sys.exit(1)


if __name__ == "__main__":
    main()
