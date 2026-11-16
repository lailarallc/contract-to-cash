"""The shipped retailer data shows role labels, never a real partner name."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_shipped_retailer_json_uses_labels():
    labels = json.loads((ROOT / "reference" / "retailer_display_labels.json").read_text(encoding="utf-8"))
    real = {
        entry["name"]
        for group in ("retailers", "distributors")
        for entry in labels[group].values()
        if entry["name"].lower() != entry["label"].lower()
    }
    data = json.loads((ROOT / "frontend" / "public" / "json" / "retailers.json").read_text(encoding="utf-8"))
    shown = {r["name"] for r in data["leakage"]} | {r["name"] for r in data["time_to_cash"]} | set(data["deduction_mix"])
    assert not (shown & real), f"real partner names in shipped JSON: {sorted(shown & real)}"
