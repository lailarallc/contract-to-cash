"""Canonical regression tests for Cinderhaven baked JSON data.

These tests load the baked JSON files in frontend/public/json/ and assert
that key figures match the values locked in CINDERHAVEN_CANONICAL.md.
They exist to catch accidental data drift when the pipeline is re-run.

Run:
    pytest tests/test_canonical_regression.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JSON_DIR = ROOT / "frontend" / "public" / "json"

EXPECTED_JSON_FILES = ("summary.json", "lifecycle.json", "retailers.json")

# Canonical counts come from the vendored canon (refreshed from the platform by
# scripts/refresh_canonical.py), not hardcoded here.
CANON = json.loads(
    (ROOT / "reference" / "canonical_values.json").read_text(encoding="utf-8")
)
CANON_SKUS = CANON["universe"]["skus_total"]["all_time"]
CANON_RETAILERS = CANON["universe"]["retailers"]["all_time"]


class TestCinderhavenCanonicalRegression:
    """Assert baked JSON matches locked canonical figures."""

    # ------------------------------------------------------------------
    # Smoke tests — files exist and parse as valid JSON
    # ------------------------------------------------------------------

    @pytest.mark.parametrize("filename", EXPECTED_JSON_FILES)
    def test_json_file_exists(self, filename: str) -> None:
        path = JSON_DIR / filename
        assert path.exists(), f"{filename} not found at {path}"

    @pytest.mark.parametrize("filename", EXPECTED_JSON_FILES)
    def test_json_file_is_valid(self, filename: str) -> None:
        path = JSON_DIR / filename
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)  # will raise on invalid JSON
        assert data, f"{filename} parsed but is empty"

    # ------------------------------------------------------------------
    # Summary meta — exact canonical counts
    # ------------------------------------------------------------------

    @pytest.fixture()
    def summary(self) -> dict:
        return json.loads((JSON_DIR / "summary.json").read_text(encoding="utf-8"))

    @pytest.fixture()
    def lifecycle(self) -> dict:
        return json.loads((JSON_DIR / "lifecycle.json").read_text(encoding="utf-8"))

    def test_skus_equals_50(self, summary: dict) -> None:
        assert summary["meta"]["skus"] == CANON_SKUS, (
            f"Expected {CANON_SKUS} SKUs (canon), got {summary['meta']['skus']}"
        )

    def test_retailers_b2b_equals_6(self, summary: dict) -> None:
        assert summary["meta"]["retailers_b2b"] == CANON_RETAILERS, (
            f"Expected {CANON_RETAILERS} B2B retailers (canon), got "
            f"{summary['meta']['retailers_b2b']}"
        )

    def test_no_flattened_retailer_count(self, summary: dict) -> None:
        """Canonical: "6 retail partners + DTC", never a flattened "7".

        DTC is not a retailer, so the export must not ship a combined
        retailers_total that counts it as one (drift item the canonical
        names explicitly; superseded 2026-07)."""
        assert "retailers_total" not in summary["meta"], (
            "meta.retailers_total flattens 6 retailers + DTC into one count; "
            "the canonical phrasing is '6 retail partners + DTC'"
        )

    # ------------------------------------------------------------------
    # Lifecycle — ~86 cents per dollar (canonical headline figure)
    # ------------------------------------------------------------------

    def test_cents_per_dollar_matches_canonical(self, summary: dict) -> None:
        """Lifecycle yield on CY2023-2025 equals the canon key
        lifecycle.retailer_dtc_cents_per_dollar.trailing_36m (owner, 2026-11-17),
        not a typed literal. The history below is superseded.

        CINDERHAVEN_CANONICAL.md (VERIFIED-AGAINST-PRODUCTION 2026-07-29)
        pins the lifecycle at 87.2 cents retailer / 87.3 combined, superseding
        the earlier 86.38 waterfall figure and the dead 82.8 CY2024 cut.
        Lifecycle cents are documented in the canonical .md (not the YAML),
        so this is a cited literal, ±0.5 per check_canonical rate tolerance.
        """
        cpd = summary["combined"]["cents_per_dollar"]
        key = CANON["lifecycle"]["retailer_dtc_cents_per_dollar"]["trailing_36m"]
        assert cpd == round(key, 1), (
            f"Expected {round(key, 1)} cents per dollar (canon key), got {cpd}"
        )

    def test_cents_per_dollar_matches_ratio(self, summary: dict) -> None:
        """cents_per_dollar should equal total_net / total_invoiced * 100,
        matching the canonical computation."""
        combined = summary["combined"]
        computed = round(combined["total_net"] / combined["total_invoiced"] * 100, 1)
        assert combined["cents_per_dollar"] == computed, (
            f"cents_per_dollar ({combined['cents_per_dollar']}) does not match "
            f"computed ratio ({computed})"
        )

    def test_lifecycle_b2b_waterfall_sums_correctly(self, lifecycle: dict) -> None:
        """gross - sum(stages) should equal net for the B2B lifecycle."""
        b2b = lifecycle["b2b"]
        stage_total = sum(s["amount"] for s in b2b["stages"])
        computed_net = round(b2b["gross"] - stage_total, 2)
        assert b2b["net"] == computed_net, (
            f"B2B waterfall does not balance: gross {b2b['gross']} - "
            f"stages {stage_total} = {computed_net}, but net is {b2b['net']}"
        )
