# Contract-to-Cash — Decisions Log

Permanent record of choices that should survive session turnover.
If a decision is reversed, strike it through and add the replacement
below — don't delete.

---

## Format

Each entry:
- **Date** — when decided
- **Decision** — one sentence, imperative voice
- **Why** — the reasoning, including what was tried and rejected
- **Scope** — what this applies to (file, chunk, deliverable, or "global")
- **Do not** — explicit anti-instructions, if any

---

## Architecture & Pipeline

### 2026-05-16 — Use Recharts for waterfall chart
- **Decision:** Use Recharts (not D3) for the anchor waterfall and supporting charts.
- **Why:** The anchor visual is a standard waterfall — no custom path geometry needed. Recharts handles bar/waterfall with less boilerplate than D3, matches short-ship-cost's pattern, and produces SVG for print. D3 would be warranted for a Sankey or force layout, but exploration revealed waterfall is the right chart type.
- **Scope:** frontend/src/components/
- **Do not:** Use D3 unless a chart type emerges that Recharts cannot handle.

---

## Data & Schema

### 2026-05-16 — Revenue frame is fct_payments.gross_amount (not fct_orders.line_total)
- **Decision:** The C2C lifecycle starts at payment-level gross, not invoice totals.
- **Why:** fct_payments.gross_amount ($17.43M) represents what retailers acknowledged they owed. fct_orders.line_total ($31.41M) includes orders not yet paid (AR). The headline uses both — the *invoice-to-cash gap* is the hook, but the *waterfall breakdown* uses the payment frame where we can trace exactly what was deducted.
- **Scope:** All lifecycle calculations, export script, narrative text.
- **Do not:** Present $31.41M as "revenue" without qualifying it as "invoiced."

### ~~2026-05-16 — DTC payment data lives in raw schema (not dbt-governed)~~
~~- **Decision:** DTC payment tables (shopify_transactions, shopify_refunds, shopify_chargebacks, shopify_payouts) written directly to the raw schema in Postgres.~~
~~- **Why:** Faster to iterate during C2C development. Adding dbt models/sources would require changes to cinderhaven-data-platform. The export script queries raw directly. If other projects need DTC payments, governance can be added later.~~
~~- **Scope:** scripts/generate_dtc_payments.py, scripts/export_json.py~~
~~- **Do not:** Modify cinderhaven-data-platform dbt models for C2C-only needs.~~
Superseded 2026-11-17: the platform now seeds these four tables; see "DTC payments are the platform's" under Reversed / Superseded.

---

## Visualization

### 2026-05-16 — Anchor visual is a waterfall chart
- **Decision:** Use a descending waterfall as the anchor visual (gross → deduction categories → net).
- **Why:** Exploration revealed 9 deduction types with clear magnitude ranking. A waterfall shows the starting amount and each category "chipping away" — the viewer literally sees money disappearing step by step. Sankey was considered but is better for flows with multiple destinations (RDR already uses one). Bar charts don't show the cumulative loss.
- **Scope:** frontend/src/components/
- **Do not:** Use a Sankey (that's RDR's visual identity).

### 2026-05-16 — Single-page scrolling narrative structure
- **Decision:** The piece is a single-page scroll with 4 sections: (1) headline + shock stat, (2) anchor waterfall, (3) retailer comparison bars, (4) time-to-cash insight.
- **Why:** The story has a clear arc: shock → breakdown → comparison → timing. A single scroll delivers all three audience reactions (R3) in sequence without navigation. Dashboard-style tabbing would fight the narrative constraint (R10).
- **Scope:** frontend/src/App.tsx
- **Do not:** Add tabs, filters, or multi-page navigation.

### 2026-05-16 — Headline: "For Every Dollar Invoiced, Fifty-One Cents Arrives as Cash"
- **Decision:** Use this Economist-style provocative headline.
- **Why:** $15.9M net / $31.4M invoiced = 50.6%. This framing is immediately shocking — it combines AR timing and deductions into a single devastating ratio. It differentiates instantly from RDR (which focuses on deduction recovery, not the full lifecycle). The specificity ("fifty-one cents") is more arresting than a percentage.
- **Scope:** frontend/src/App.tsx (hero section)
- **Do not:** Hedge the headline. The data supports it. Caveats go in supporting text.

---

## Deployment

### 2026-05-16 — Deploy to Cloudflare Pages via wrangler
- **Decision:** Ship the SPA as a Cloudflare Workers static site using wrangler deploy from frontend/.
- **Why:** Zero-config static hosting with global CDN. SPA not_found_handling routes all paths to index.html. No server-side logic needed — all data is pre-exported JSON. Workers domain (cash.lailarallc.com) serves as the portfolio URL.
- **Scope:** frontend/wrangler.jsonc, deployment workflow.
- **Do not:** Add a custom domain until the piece is reviewed and finalized.

### 2026-05-16 — Exclude distributors (KeHE, UNFI) from analysis
- **Decision:** Filter all B2B queries by `dim_retailers.channel_type = 'retailer'`, excluding distributors entirely.
- **Why:** Distributors are intermediaries — retailers buy from them. Including distributor payments alongside direct retail payments mixes fundamentally different commercial relationships. The analysis is about what Cinderhaven nets from its retail partners, not from middlemen.
- **Scope:** scripts/export_json.py, all B2B queries, all JSON output.
- **Do not:** Re-add distributors. If distributor analysis is needed, it's a separate piece.

### 2026-05-16 — Scope analysis to Calendar Year 2025
- **Decision:** All queries filter to Jan 1 – Dec 31, 2025.
- **Why:** An 18-month window is unrealistic for a revenue lifecycle review. CFOs look at a fiscal year or quarter. CY2025 is a clean annual frame that produces meaningful numbers ($15.6M invoiced, 59 cents per dollar).
- **Scope:** scripts/export_json.py (PERIOD_START, PERIOD_END constants), all JSON output.
- **Do not:** Use unbounded date ranges. If a different period is needed, change the constants.

### ~~2026-05-16 — Net Received bar in kelly green (#2D8E47)~~
- ~~**Decision:** The waterfall chart's Net Received bar uses kelly green, not teal.~~
- ~~**Why:** The teal gradient shows deductions "chipping away." The final net bar is the result — it needs to visually stand out as a different category (outcome vs. process). Green signals "what you kept."~~
- ~~**Scope:** frontend/src/components/WaterfallChart.tsx~~
- ~~**Do not:** Use navy, steel, or teal for the net bar.~~
- **Superseded by:** 2026-05-22 — Net Received bar in Chicago-20 navy

### 2026-05-22 — Net Received bar in Chicago-20 navy (#1f2e7a)
- **Decision:** The waterfall chart's Net Received bar uses Chicago-20 navy from the Lailara Design System.
- **Why:** Kelly green (#2D8E47) was off-palette — not traceable to any Lailara Design System family. Chicago-20 navy provides the same categorical distinction (outcome vs. deduction process) while staying on-palette. Navy is the design system's primary accent color.
- **Scope:** frontend/src/components/WaterfallChart.tsx
- **Do not:** Use off-palette colors for chart elements.

### 2026-05-22 — Shared chart constants in chartConstants.ts
- **Decision:** All chart color scales, formatting helpers, and color-picking functions live in `frontend/src/chartConstants.ts`. Python DB helpers live in `scripts/db.py`.
- **Why:** Three chart components and four Python scripts each had identical copies. Centralization eliminates drift and makes design system updates one-line changes.
- **Scope:** frontend/src/components/, scripts/
- **Do not:** Duplicate TEAL_SCALE, formatDollars, or DEC2FLOAT/connect in individual files.

### 2026-05-22 — Waterfall uses explicit "Unclassified Shortfall" stage for unaccounted gross-net gap
- **Decision:** When categorized deductions don't account for the full gross-net gap, compute and append an "Unclassified Shortfall" catch-all stage.
- **Why:** Categorized deductions from `fct_retailer_deductions` only capture a fraction of the payment-level gross-net gap from `fct_retailer_payments`. Hiding the difference would make the waterfall dishonest. Distributing it across existing categories would misrepresent their magnitudes.
- **Scope:** B2B waterfall in lifecycle.json and WaterfallChart.tsx
- **Do not:** Distribute unaccounted shortfall across existing deduction categories or silently drop it.

### 2026-05-20 — All colors must come from Lailara Design System families
- **Decision:** Every color in this project must trace to a Lailara Design System family and step number (Hong Kong teal, London greyscale, Chicago blue, Red).
- **Why:** Previous colors were close but freehand. Aligning to the city-named families ensures brand consistency across all Lailara portfolio pieces.
- **Scope:** frontend/src/styles.css, all chart components
- **Do not:** Use arbitrary hex values. Every color must trace to a family and step number from the design system.

---

## Output Formats

---

## Writing & Voice

### 2026-11-15 — Role labels replace partner names; retailers.json golden re-baselined

- **Decision (owner, 2026-11-15, "do A"):** the report shows a role label for each trade partner (national mass retailer, club retailer, and so on), never the real name. The label is applied on export in `scripts/export_json.py` from `reference/retailer_display_labels.json`, so the shipped `frontend/public/json/retailers.json` carries labels too, not only the screen.
- **Why:** the fleet label rule (lailara-website DECISIONS 2026-11-05). The data file pairs each partner with dollar amounts and is publicly readable. A screen-only swap would have left the names in it.
- **Golden:** `tests/test_demo_golden.py` pins the file's content. The `retailers` SHA moved from `04b99dd2…` to `6d43adde…` and was re-baselined with this approval. Only the six names changed; every number is identical (checked by comparing the old and new files with names removed).
- **Not done:** the export was not re-run against the database; the same mapping was applied to the committed file. `tests/test_retailer_labels.py` fails if a real partner name returns.
- **Do not:** show a real partner name beside a Cinderhaven figure on any public surface of this repo.

---

## Reversed / Superseded

When a decision is overturned:
1. Strike through the original entry above (don't delete)
2. Add a new entry below with the replacement decision
3. Note the link in both directions

This preserves the history of why something is the way it is.

### 2026-11-17 — DTC payments are the platform's; this repo writes no warehouse table
- **Decision:** `scripts/generate_dtc_payments.py` is retired. The export and the cross-project validator read the platform's `raw.shopify_transactions`, `_refunds`, `_chargebacks` and `_payouts`, which the platform's own seed writes (`generation/seed_dtc.py`).
- **Why:** Cinderhaven regen plan U19a: no consumer writes a platform schema. Production's four tables are the platform's (owner `cinderhaven_generator`, platform columns; reader run 44197063903), and the committed `summary.json` fees, refunds and lost chargebacks equal the platform tables' to the cent. The generator could no longer run: it reads `order_total` from `fct_dtc_orders`, which has no such column. Moving it to a schema of its own would have changed the printed DTC figures; retiring it changes none.
- **Scope:** scripts/generate_dtc_payments.py (deleted), README script table.
- **Do not:** write DTC payment rows from this repo. A figure the platform does not produce is a request to the platform.
