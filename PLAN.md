# Contract-to-Cash — Current Work Plan

The current arc of work. Updated when the arc changes, not every
session. For session-by-session state, see HANDOFF.md.

---

## Goal

Build a portfolio piece that tells the complete money-leak story for a mid-market specialty food brand ($52.7M invoiced over the 36-month window the tool ships) — tracing where revenue evaporates between contract and cash receipt. React SPA (Vite, Cloudflare Pages), static JSON data from the Cinderhaven Data Platform. Audience is CEO/CFO. The specific visual approach and narrative structure emerge from data exploration, not prescribed upfront.

## Why this arc, why now

Second buyer-facing consumer of the Cinderhaven Data Platform. Demonstrates revenue operations fluency to C-suite buyers. Platform dependency resolved — substrate is live. Building in parallel with channel-profitability-analysis (may ship first).

## Business question this arc answers

On that deal we signed in Q1 — what did we actually net, and where did the money leak between systems?

## Constraints

- All Cinderhaven numbers must reconcile with CINDERHAVEN_CANONICAL.md. Shipped 36-month (2023–2026) window: $52.7M invoiced ($52.1M B2B + $0.6M DTC), 50 SKUs, 6 B2B retailers + DTC in this tool's scope, 14,947 retailer deductions. (The $25M / 90 SKUs / 11 retailers / 3,087 deductions figures here were pre-reseed canon.)
- No Streamlit
- Business story first, claims backed by rigorous analysis
- New synthetic data is acceptable if needed, but must be additive and consistent with existing projects
- Quality over speed, no hard deadline

## Tasks

- [x] Run /clarify to scope the work
- [x] Explore platform data — find the story, identify gaps
- [x] Synthesize DTC payment lifecycle data
- [x] Cross-project reconciliation validation (17 checks pass)
- [x] Define narrative structure and visual approach based on findings
- [x] Build Python export script (summary.json, lifecycle.json, retailers.json)
- [x] Scaffold React SPA (Vite + TypeScript + Recharts + CF Pages)
- [x] Implement anchor waterfall + narrative sections
- [x] Polish, validate, deploy to Cloudflare Pages

## Out of scope for this arc

- Streamlit or server-rendered apps
- DE proof (platform handles that)
- Marketing/LinkedIn content
- Rebuilding platform infrastructure
- Anything that doesn't serve the story

## Definition of done for this arc

- [x] Fully deployed React SPA on Cloudflare Pages
- [x] Complete, compelling money-leak narrative backed by data
- [x] Numbers reconcile with all other Cinderhaven projects
- [x] CFO/CEO can understand the story without technical background

---

## Arc history

---

## Improvement history

### 2026-05-22 — Improvement pass

- **Trigger:** User-initiated after code review and test addition
- **What was reviewed:** Code quality, tests, dependencies, documentation, git hygiene, security, data reconciliation, workflow files
- **Findings:** 3 critical, 4 important, 3 nice-to-have
- **What was fixed (all 10):**
  1. Closed $1.7M waterfall gap — added Unclassified Shortfall stage
  2. Updated stale README (all numbers matched to current JSON)
  3. Fixed validation script — 29/29 checks pass
  4. Hardened db.py — schema allowlist + require credentials
  5. Aligned DTC chargeback_fee between export and validation
  6. Expanded .gitignore (secrets patterns)
  7. Added security headers (_headers file)
  8. Populated FAILURES.md (3 entries)
  9. Annotated stale HANDOFF numbers with current figures
  10. Added test suites (11 vitest + 7 pytest, all passing)
- **Deferred:** None — all findings addressed
- **Next review:** 2026-06-22

### 2026-09-23 — Audit (health check only)
- **Findings:** 1 critical, 5 important, 4 nice-to-have
- **Top concerns:** Client mode (client_mode.py) counts unpaid invoices (blank payment_date, amount_received 0) as fully leaked, so open receivables inflate leakage and deflate cents-per-dollar in client deliverables. The demo headline generator truncates instead of rounding (int(cents)), and the page copy is inconsistent: it cites a "post-audit" category that does not exist and calls the residual both "payment-timing" and "un-itemized trade spend". The deployed SPA also lacks the Lailara brand frame, and HANDOFF.md is two months and ~25 commits stale.
- **Action taken:** Audit only — no fixes this session
- **Next review:** 2026-12-22
