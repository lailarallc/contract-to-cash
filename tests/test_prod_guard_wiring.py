"""The prod guard sits in front of the Postgres write path.

`scripts/generate_dtc_payments.py` drops and recreates raw.shopify_* tables at
whatever DATABASE_URL points to -- localhost:5432 is a `fly proxy` tunnel to
production when one is open. These tests fake a flyctl listener and assert
nothing connects.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import generate_dtc_payments  # noqa: E402
import prod_guard  # noqa: E402


def test_connect_refuses_fly_tunnel_before_connecting(monkeypatch):
    seen = []
    monkeypatch.delenv("ALLOW_PROD_DB", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u@localhost:15432/cinderhaven")
    # Fake the port owner: a real netstat lookup would depend on this machine's state.
    monkeypatch.setattr(prod_guard, "_listener", lambda port: seen.append(port) or "flyctl")
    monkeypatch.setattr(generate_dtc_payments.psycopg2, "connect",
                        lambda *a, **kw: pytest.fail("connected"))
    with pytest.raises(prod_guard.ProdDatabaseError):
        generate_dtc_payments.connect()
    assert seen == [15432], f"guard checked ports {seen}, expected the DATABASE_URL port"
