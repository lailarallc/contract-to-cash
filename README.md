# Contract to Cash

Revenue lifecycle analysis for a mid-market CPG brand — tracing where money leaks between invoice and cash receipt.

**Live:** https://cash.lailarallc.com

## What it does

A single-page narrative that answers the question the CFO of a specialty food brand invoicing $52.7M over three years cannot: *On that deal we signed in Q1 — what did we actually net, and where did the money leak between systems?*

The piece traces $52.7M invoiced across 6 retail partners and a DTC channel through deductions, processing fees, refunds, and timing delays over a 36-month window. Three charts tell the story:

1. **Waterfall** — gross B2B payments descending through 9 deduction categories plus an unreconciled residual to net received
2. **Retailer comparison** — leakage rates from 10.0% to 15.7% across 6 direct retail partners
3. **Time-to-cash** — average days from order to payment, ranging 23.9–28.3 days by retailer

Economist-style visual language: minimal gridlines, text labels on every data point, no decoration. Written in sober, declarative prose.

## Why it matters

For every dollar Cinderhaven invoiced over the 36-month window, eighty-seven cents arrived as cash. The missing thirteen cents is not one line item — it is spread across deduction categories, payment processors, refunds, and float, in systems that don't reconcile against each other. Making that leakage visible by channel and by retailer shows a finance team exactly where recovery effort pays off, and how much working capital is tied up in time-to-cash.

For a due-diligence reviewer, the project also demonstrates auditability: every figure in the published page traces to a specific SQL query, and 46 automated checks reconcile the exported data against the canonical platform numbers.

## Quick start

**Frontend** (no database required — consumes pre-exported static JSON):

```sh
cd frontend
npm install
npm run dev
```

Opens at `http://localhost:5173`.

**Data pipeline** (requires Cinderhaven Postgres access):

```sh
pip install -r scripts/requirements.txt
DATABASE_URL=postgresql://... python scripts/export_json.py
python scripts/validate_exported_json.py
```

**Deploy:**

```sh
cd frontend
npm run deploy
```

## Tech stack

- **Frontend:** React 19, TypeScript 6, Vite 8, Recharts 2.15
- **Deployment:** Cloudflare Workers (static assets, SPA routing)
- **Data pipeline:** Python 3, psycopg2, Cinderhaven Data Platform (Postgres)
- **Design system:** Lailara Design System (self-hosted fonts — Playfair Display, Source Sans 3 — teal palette, Economist chart rules)

## Project structure

```
Cinderhaven Data Platform (Postgres)
    │
    ├─ scripts/export_json.py ──→ frontend/public/json/ (3 static JSON files)
    │
    └─ scripts/validate_*.py ──→ 46 reconciliation + consistency checks
                                    (17 cross-project, 29 exported JSON)

frontend/ (React SPA, deployed to Cloudflare Workers)
```

| Script | Purpose |
|--------|---------|
| `scripts/explore_lifecycle.py` | Exploration queries (discovery phase) |
| `scripts/export_json.py` | Production export: Postgres → JSON (36-month window, B2B + DTC) |
| `scripts/validate_cross_project.py` | Reconciliation against other Cinderhaven projects (17 checks) |
| `scripts/validate_exported_json.py` | Internal consistency of exported JSON (29 checks) |

The SPA consumes pre-aggregated static JSON — no runtime database connection.

## Part of the Cinderhaven portfolio

This is the second buyer-facing project built on the Cinderhaven Data Platform. It tells the full revenue lifecycle story — differentiated from [Retailer Deduction Recovery](https://github.com/MsShawnP/retailer-deduction-recovery), which covers deduction recovery in depth.

## License

MIT — see [LICENSE](LICENSE).

---
Built by [Lailara LLC](https://lailarallc.com) — data hygiene and analytics consulting for specialty food brands scaling into national retail.
