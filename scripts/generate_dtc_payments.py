"""Generate synthetic Shopify payment lifecycle data for existing DTC orders.

Reads the 10K DTC orders from the Cinderhaven platform and generates:
  - shopify_transactions: per-order payment processing records (fees, net)
  - shopify_refunds: refund events (~4% of orders)
  - shopify_chargebacks: chargeback events (~0.8% of orders, with $15 fee)
  - shopify_payouts: daily bank payout batches

Writes to the 'raw' schema in Postgres (additive, no existing tables modified).

Usage:
    DATABASE_URL=postgresql://... python scripts/generate_dtc_payments.py
"""

from __future__ import annotations

import os
import random
import sys
from datetime import date, timedelta

import psycopg2
import psycopg2.extras

from db import DEC2FLOAT  # noqa: F401 — registered at import time
import prod_guard

SEED = 42

SHOPIFY_RATE = 0.029
SHOPIFY_FIXED = 0.30
CHARGEBACK_FEE = 15.00

REFUND_RATE = 0.04
PARTIAL_REFUND_SHARE = 0.40
CHARGEBACK_RATE = 0.008

PAYOUT_CYCLE_DAYS = 2


def connect():
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)
    prod_guard.check(url)  # refuses a fly tunnel to production
    return psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)


def log(msg):
    print(msg, flush=True)


def main():
    rng = random.Random(SEED)
    log("Connecting to database...")
    conn = connect()
    cur = conn.cursor()
    cur.execute("SET search_path TO raw, public_marts, public")
    conn.commit()
    log("Connected. Loading DTC orders...")

    # Load existing DTC orders from the platform (order grain, not line grain).
    cur.execute("""
        SELECT DISTINCT order_id, order_date, order_total
        FROM public_marts.fct_dtc_orders
        ORDER BY order_date, order_id
    """)
    orders = cur.fetchall()
    if not orders:
        print("ERROR: No DTC orders found in fct_dtc_orders", file=sys.stderr)
        sys.exit(1)
    log(f"Loaded {len(orders):,} DTC orders from platform")

    total_order_revenue = sum(o["order_total"] for o in orders)
    log(f"Total DTC order revenue: ${total_order_revenue:,.2f}")

    # ─── Create tables ────────────────────────────────────────────────────
    log("Creating tables...")

    cur.execute("DROP TABLE IF EXISTS raw.shopify_payouts CASCADE")
    cur.execute("DROP TABLE IF EXISTS raw.shopify_chargebacks CASCADE")
    cur.execute("DROP TABLE IF EXISTS raw.shopify_refunds CASCADE")
    cur.execute("DROP TABLE IF EXISTS raw.shopify_transactions CASCADE")

    cur.execute("""
        CREATE TABLE raw.shopify_transactions (
            transaction_id   TEXT PRIMARY KEY,
            order_id         TEXT NOT NULL,
            transaction_date DATE NOT NULL,
            order_amount     NUMERIC(12,2) NOT NULL,
            processing_fee   NUMERIC(12,2) NOT NULL,
            net_amount       NUMERIC(12,2) NOT NULL,
            payment_method   TEXT NOT NULL,
            status           TEXT NOT NULL DEFAULT 'completed'
        )
    """)

    cur.execute("""
        CREATE TABLE raw.shopify_refunds (
            refund_id        TEXT PRIMARY KEY,
            order_id         TEXT NOT NULL,
            refund_date      DATE NOT NULL,
            refund_amount    NUMERIC(12,2) NOT NULL,
            refund_type      TEXT NOT NULL,
            reason           TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE raw.shopify_chargebacks (
            chargeback_id    TEXT PRIMARY KEY,
            order_id         TEXT NOT NULL,
            chargeback_date  DATE NOT NULL,
            chargeback_amount NUMERIC(12,2) NOT NULL,
            chargeback_fee   NUMERIC(12,2) NOT NULL,
            reason           TEXT NOT NULL,
            outcome          TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE raw.shopify_payouts (
            payout_id        TEXT PRIMARY KEY,
            payout_date      DATE NOT NULL,
            gross_amount     NUMERIC(12,2) NOT NULL,
            fees_amount      NUMERIC(12,2) NOT NULL,
            refunds_amount   NUMERIC(12,2) NOT NULL,
            chargebacks_amount NUMERIC(12,2) NOT NULL,
            net_amount       NUMERIC(12,2) NOT NULL,
            transaction_count INTEGER NOT NULL,
            status           TEXT NOT NULL DEFAULT 'paid'
        )
    """)
    conn.commit()

    # ─── Generate transaction fees ────────────────────────────────────────

    transactions = []
    payment_methods = ["credit_card", "debit_card", "shop_pay", "apple_pay"]
    method_weights = [50, 20, 20, 10]

    for o in orders:
        order_amt = float(o["order_total"])
        fee = round(order_amt * SHOPIFY_RATE + SHOPIFY_FIXED, 2)
        net = round(order_amt - fee, 2)
        method = rng.choices(payment_methods, weights=method_weights, k=1)[0]
        txn_id = f"TXN-{o['order_id']}"
        transactions.append((
            txn_id, o["order_id"], o["order_date"],
            order_amt, fee, net, method, "completed"
        ))

    psycopg2.extras.execute_values(
        cur,
        """INSERT INTO raw.shopify_transactions
            (transaction_id, order_id, transaction_date, order_amount,
             processing_fee, net_amount, payment_method, status)
        VALUES %s""",
        transactions,
        page_size=1000,
    )

    total_fees = sum(t[4] for t in transactions)
    print(f"\nTransactions: {len(transactions):,}")
    print(f"  Total processing fees: ${total_fees:,.2f} "
          f"({total_fees / total_order_revenue * 100:.1f}% of revenue)")

    # ─── Generate refunds ─────────────────────────────────────────────────

    refund_reasons = [
        ("product_damaged", 0.30),
        ("wrong_item", 0.20),
        ("not_as_described", 0.15),
        ("changed_mind", 0.25),
        ("late_delivery", 0.10),
    ]
    reason_names = [r[0] for r in refund_reasons]
    reason_weights = [r[1] for r in refund_reasons]

    refund_count = int(len(orders) * REFUND_RATE)
    refund_orders = rng.sample(orders, refund_count)
    refunds = []

    for i, o in enumerate(refund_orders):
        order_amt = float(o["order_total"])
        is_partial = rng.random() < PARTIAL_REFUND_SHARE
        if is_partial:
            refund_pct = rng.uniform(0.20, 0.60)
            refund_amt = round(order_amt * refund_pct, 2)
            refund_type = "partial"
        else:
            refund_amt = order_amt
            refund_type = "full"

        days_after = rng.randint(3, 30)
        refund_date = o["order_date"] + timedelta(days=days_after)
        reason = rng.choices(reason_names, weights=reason_weights, k=1)[0]
        refund_id = f"REF-{i + 1:05d}"

        refunds.append((
            refund_id, o["order_id"], refund_date,
            refund_amt, refund_type, reason
        ))

    psycopg2.extras.execute_values(
        cur,
        """INSERT INTO raw.shopify_refunds
            (refund_id, order_id, refund_date, refund_amount, refund_type, reason)
        VALUES %s""",
        refunds,
        page_size=500,
    )

    total_refunded = sum(r[3] for r in refunds)
    print(f"\nRefunds: {len(refunds):,} ({len(refunds) / len(orders) * 100:.1f}% of orders)")
    print(f"  Total refunded: ${total_refunded:,.2f}")
    print(f"  Partial: {sum(1 for r in refunds if r[4] == 'partial'):,}, "
          f"Full: {sum(1 for r in refunds if r[4] == 'full'):,}")

    # ─── Generate chargebacks ─────────────────────────────────────────────

    refunded_order_ids = {r[1] for r in refunds}
    chargeback_eligible = [o for o in orders if o["order_id"] not in refunded_order_ids]
    chargeback_count = int(len(orders) * CHARGEBACK_RATE)
    chargeback_orders = rng.sample(chargeback_eligible, min(chargeback_count, len(chargeback_eligible)))

    chargeback_reasons = [
        ("fraudulent", 0.35),
        ("product_not_received", 0.25),
        ("not_as_described", 0.20),
        ("duplicate_charge", 0.10),
        ("subscription_canceled", 0.10),
    ]
    cb_reason_names = [r[0] for r in chargeback_reasons]
    cb_reason_weights = [r[1] for r in chargeback_reasons]

    chargeback_outcomes = [
        ("lost", 0.55),
        ("won", 0.30),
        ("pending", 0.15),
    ]
    cb_outcome_names = [r[0] for r in chargeback_outcomes]
    cb_outcome_weights = [r[1] for r in chargeback_outcomes]

    chargebacks = []
    for i, o in enumerate(chargeback_orders):
        order_amt = float(o["order_total"])
        days_after = rng.randint(14, 90)
        cb_date = o["order_date"] + timedelta(days=days_after)
        reason = rng.choices(cb_reason_names, weights=cb_reason_weights, k=1)[0]
        outcome = rng.choices(cb_outcome_names, weights=cb_outcome_weights, k=1)[0]
        cb_id = f"CB-{i + 1:05d}"

        chargebacks.append((
            cb_id, o["order_id"], cb_date,
            order_amt, CHARGEBACK_FEE, reason, outcome
        ))

    psycopg2.extras.execute_values(
        cur,
        """INSERT INTO raw.shopify_chargebacks
            (chargeback_id, order_id, chargeback_date, chargeback_amount,
             chargeback_fee, reason, outcome)
        VALUES %s""",
        chargebacks,
        page_size=500,
    )

    cb_lost = [c for c in chargebacks if c[6] == "lost"]
    total_cb_lost = sum(c[3] for c in cb_lost)
    total_cb_fees = sum(c[4] for c in chargebacks)
    print(f"\nChargebacks: {len(chargebacks):,} ({len(chargebacks) / len(orders) * 100:.2f}% of orders)")
    print(f"  Lost: {len(cb_lost):,} (${total_cb_lost:,.2f})")
    print(f"  Won: {sum(1 for c in chargebacks if c[6] == 'won'):,}")
    print(f"  Pending: {sum(1 for c in chargebacks if c[6] == 'pending'):,}")
    print(f"  Total chargeback fees: ${total_cb_fees:,.2f}")

    # ─── Generate payouts ─────────────────────────────────────────────────

    txn_by_date = {}
    for t in transactions:
        d = t[2]
        if d not in txn_by_date:
            txn_by_date[d] = {"gross": 0, "fees": 0, "count": 0}
        txn_by_date[d]["gross"] += t[3]
        txn_by_date[d]["fees"] += t[4]
        txn_by_date[d]["count"] += 1

    refund_by_date = {}
    for r in refunds:
        d = r[2]
        refund_by_date[d] = refund_by_date.get(d, 0) + r[3]

    cb_by_date = {}
    for c in chargebacks:
        if c[6] == "lost":
            d = c[2]
            cb_by_date[d] = cb_by_date.get(d, 0) + c[3] + c[4]

    all_dates = sorted(set(list(txn_by_date.keys()) + list(refund_by_date.keys()) + list(cb_by_date.keys())))
    if not all_dates:
        print("WARNING: No dates to generate payouts for")
    else:
        payout_id_counter = 1
        payouts = []
        batch_gross = 0
        batch_fees = 0
        batch_refunds = 0
        batch_cbs = 0
        batch_count = 0
        batch_start = all_dates[0]

        for d in all_dates:
            day_txn = txn_by_date.get(d, {"gross": 0, "fees": 0, "count": 0})
            batch_gross += day_txn["gross"]
            batch_fees += day_txn["fees"]
            batch_refunds += refund_by_date.get(d, 0)
            batch_cbs += cb_by_date.get(d, 0)
            batch_count += day_txn["count"]

            days_since_start = (d - batch_start).days
            if days_since_start >= PAYOUT_CYCLE_DAYS or d == all_dates[-1]:
                payout_date = d + timedelta(days=PAYOUT_CYCLE_DAYS)
                net = round(batch_gross - batch_fees - batch_refunds - batch_cbs, 2)
                po_id = f"PO-{payout_id_counter:05d}"
                payouts.append((
                    po_id, payout_date,
                    round(batch_gross, 2), round(batch_fees, 2),
                    round(batch_refunds, 2), round(batch_cbs, 2),
                    net, batch_count, "paid"
                ))
                payout_id_counter += 1
                batch_gross = 0
                batch_fees = 0
                batch_refunds = 0
                batch_cbs = 0
                batch_count = 0
                batch_start = d + timedelta(days=1)

        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO raw.shopify_payouts
                (payout_id, payout_date, gross_amount, fees_amount,
                 refunds_amount, chargebacks_amount, net_amount,
                 transaction_count, status)
            VALUES %s""",
            payouts,
            page_size=500,
        )

        total_payout_net = sum(p[6] for p in payouts)
        print(f"\nPayouts: {len(payouts):,} batches")
        print(f"  Total net paid out: ${total_payout_net:,.2f}")

    conn.commit()

    # ─── Summary ──────────────────────────────────────────────────────────

    print("\n" + "=" * 60)
    print("  DTC PAYMENT LIFECYCLE SUMMARY")
    print("=" * 60)
    print(f"\n  Gross order revenue:     ${total_order_revenue:,.2f}")
    print(f"  Processing fees:         ${total_fees:,.2f} ({total_fees / total_order_revenue * 100:.1f}%)")
    print(f"  Refunds:                 ${total_refunded:,.2f} ({total_refunded / total_order_revenue * 100:.1f}%)")
    print(f"  Chargebacks (lost):      ${total_cb_lost:,.2f} ({total_cb_lost / total_order_revenue * 100:.1f}%)")
    print(f"  Chargeback fees:         ${total_cb_fees:,.2f}")
    total_leakage = total_fees + total_refunded + total_cb_lost + total_cb_fees
    net_received = total_order_revenue - total_leakage
    print(f"  ---")
    print(f"  Total DTC leakage:       ${total_leakage:,.2f} ({total_leakage / total_order_revenue * 100:.1f}%)")
    print(f"  Net cash received:       ${net_received:,.2f}")
    print(f"\n  DTC as % of combined revenue: "
          f"{total_order_revenue / (total_order_revenue + 31_409_072.52) * 100:.1f}%")  # B2B revenue from fct_retailer_orders
    print(f"  (Note: DTC is small relative to B2B — realistic for a")
    print(f"   primarily wholesale CPG brand with nascent DTC channel)")

    conn.close()
    print("\n  Tables written to raw schema in Postgres.")
    print("=" * 60)


if __name__ == "__main__":
    main()
