"""Demo golden lock — contract-to-cash.

The deployed narrative renders the three committed JSON in frontend/public/json/.
This locks their full content (canonical-serialized SHA-256, so it is stable
across line-ending/formatting differences) so the client-mode conversion — which
is purely additive (a new client_mode.py; nothing here regenerates the JSON) —
cannot drift the published site or the portfolio numbers.

The headline figures are additionally pinned in test_canonical_regression.py.
If a SHA here moves, STOP: a demo golden moved — do not re-baseline without a
logged approval.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

JSON_DIR = Path(__file__).resolve().parent.parent / "frontend" / "public" / "json"

# Canonical-content SHA-256 (json.dumps sorted, compact) pinned 2026-08-05.
GOLDEN = {
    "summary": "7196b164c0e05d5223606155a2ebff2437d50c03988f44cb4d0594e9aba3107e",
    # Re-baselined 2026-11-15, owner approved (DECISIONS.md): partner names
    # replaced by role labels. Names only; every number is unchanged.
    "retailers": "6d43addebcad39f5b688f97a85e7e492cccc36a7d0ec3ce3933321e20e01da78",
    "lifecycle": "d1e007c9dd3dd2544ee156b179edf68101da485487d6e8b5d4c4d31ffee88a3f",
}


@pytest.mark.parametrize("name", sorted(GOLDEN))
def test_demo_json_content_unchanged(name):
    data = json.loads((JSON_DIR / f"{name}.json").read_text(encoding="utf-8"))
    blob = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(blob).hexdigest()
    assert digest == GOLDEN[name], (
        f"{name}.json content changed (sha256 {digest} != golden {GOLDEN[name]}). "
        "A demo golden moved — STOP and report before re-baselining."
    )


def test_headline_cents_per_dollar_is_pinned():
    summary = json.loads((JSON_DIR / "summary.json").read_text(encoding="utf-8"))
    assert summary["combined"]["cents_per_dollar"] == 87.3
    assert summary["meta"]["retailers_b2b"] == 6
