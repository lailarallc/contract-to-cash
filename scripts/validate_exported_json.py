"""Validate the exported JSON files for internal consistency.

Checks the CY2025-scoped JSON output that the SPA actually displays,
independent of the full-dataset validation in validate_cross_project.py.

Usage:
    python scripts/validate_exported_json.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JSON_DIR = ROOT / "frontend" / "public" / "json"

def main() -> None:
    failures: list[tuple[str, object, object]] = []
    checks: list[tuple[str, bool]] = []

    def check(name: str, expected: object, actual: object, tolerance: float = 0.01) -> None:
        passed = True
        if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
            if expected == 0:
                passed = actual == 0
            else:
                passed = abs(actual - expected) / abs(expected) <= tolerance
        else:
            passed = actual == expected

        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")
        if not passed:
            print(f"         Expected: {expected}")
            print(f"         Actual:   {actual}")
            failures.append((name, expected, actual))
        checks.append((name, passed))

    def check_true(name: str, condition: bool) -> None:
        status = "PASS" if condition else "FAIL"
        print(f"  [{status}] {name}")
        if not condition:
            failures.append((name, True, False))
        checks.append((name, condition))
    print("=" * 60)
    print("  EXPORTED JSON VALIDATION (CY2025 subset)")
    print("=" * 60)

    for filename in ("summary.json", "lifecycle.json", "retailers.json"):
        path = JSON_DIR / filename
        if not path.exists():
            print(f"\nERROR: {filename} not found at {path}")
            sys.exit(1)

    summary = json.loads((JSON_DIR / "summary.json").read_text())
    lifecycle = json.loads((JSON_DIR / "lifecycle.json").read_text())
    retailers = json.loads((JSON_DIR / "retailers.json").read_text())

    # --- Summary internal consistency ---
    print("\n--- Summary consistency ---\n")

    b2b = summary["b2b"]
    dtc = summary["dtc"]
    combined = summary["combined"]

    # One basis (owner, 2026-11-17): B2B gross on the remittances received in the
    # window, not b2b.invoiced (orders placed in it, some paid after it ends).
    check(
        "Combined invoiced = B2B remittance gross + DTC gross",
        combined["total_invoiced"],
        round(b2b["gross_payments"] + dtc["gross"], 2),
    )

    check(
        "Combined net = B2B net + DTC net",
        combined["total_net"],
        round(b2b["net_received"] + dtc["net_received"], 2),
    )

    check(
        "Cents per dollar = net / invoiced * 100",
        combined["cents_per_dollar"],
        round(combined["total_net"] / combined["total_invoiced"] * 100, 1),
    )

    check(
        "B2B leakage pct = (gross - net) / gross * 100",
        b2b["leakage_pct"],
        round((b2b["gross_payments"] - b2b["net_received"]) / b2b["gross_payments"] * 100, 1),
    )

    check_true(
        "Headline is non-empty and references cents",
        len(summary["headline"]) > 0 and "cent" in summary["headline"].lower(),
    )

    # --- Lifecycle internal consistency ---
    print("\n--- Lifecycle consistency ---\n")

    b2b_lc = lifecycle["b2b"]
    stage_sum = sum(s["amount"] for s in b2b_lc["stages"])

    check(
        "B2B gross - sum(stages) = net",
        b2b_lc["net"],
        round(b2b_lc["gross"] - stage_sum, 2),
    )

    check(
        "B2B lifecycle gross matches summary gross_payments",
        b2b["gross_payments"],
        b2b_lc["gross"],
    )

    check(
        "B2B lifecycle net matches summary net_received",
        b2b["net_received"],
        b2b_lc["net"],
    )

    check_true(
        "All stages have positive amounts",
        all(s["amount"] > 0 for s in b2b_lc["stages"]),
    )

    # Itemized deductions carry real records (count > 0); the gross-to-net
    # residual (count == 0) is not an itemized deduction and is excluded here —
    # the same count-based split the SPA uses. Robust to the residual's label.
    categorized = [s for s in b2b_lc["stages"] if s.get("count", 0) != 0]
    check_true(
        "Categorized stages are sorted by amount descending",
        all(
            categorized[i]["amount"] >= categorized[i + 1]["amount"]
            for i in range(len(categorized) - 1)
        ),
    )

    check(
        "B2B total_deductions matches sum of categorized stages",
        b2b["total_deductions"],
        round(sum(s["amount"] for s in categorized), 2),
    )

    dtc_lc = lifecycle["dtc"]
    dtc_stage_sum = sum(s["amount"] for s in dtc_lc["stages"])

    check(
        "DTC gross - sum(stages) = net",
        dtc_lc["net"],
        round(dtc_lc["gross"] - dtc_stage_sum, 2),
    )

    # --- Retailers internal consistency ---
    print("\n--- Retailers consistency ---\n")

    total_retailer_gross = sum(r["gross"] for r in retailers["leakage"])
    total_retailer_net = sum(r["net"] for r in retailers["leakage"])

    check(
        "Sum of retailer gross matches lifecycle B2B gross",
        b2b_lc["gross"],
        round(total_retailer_gross, 2),
    )

    check(
        "Sum of retailer net matches lifecycle B2B net",
        b2b_lc["net"],
        round(total_retailer_net, 2),
    )

    check(
        "Retailer count matches summary retailers_b2b",
        summary["meta"]["retailers_b2b"],
        len(retailers["leakage"]),
    )

    for r in retailers["leakage"]:
        check(
            f"  {r['name']}: gross - net = leakage",
            r["leakage"],
            round(r["gross"] - r["net"], 2),
        )
        check(
            f"  {r['name']}: leakage_pct = leakage/gross*100",
            r["leakage_pct"],
            round(r["leakage"] / r["gross"] * 100, 1),
        )

    check_true(
        "Time-to-cash has same retailers as leakage",
        set(r["name"] for r in retailers["time_to_cash"])
        == set(r["name"] for r in retailers["leakage"]),
    )

    check_true(
        "All time-to-cash avg_days are positive",
        all(r["avg_days"] > 0 for r in retailers["time_to_cash"]),
    )

    # --- Results ---
    print("\n" + "=" * 60)
    total = len(checks)
    passed = sum(1 for _, p in checks if p)
    failed = total - passed

    if failed == 0:
        print(f"  ALL {total} CHECKS PASSED")
        print("=" * 60)
        sys.exit(0)
    else:
        print(f"  {failed} of {total} CHECKS FAILED:")
        for name, expected, actual in failures:
            print(f"    - {name}: expected {expected}, got {actual}")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
