---
date: 2026-05-16
topic: revenue-lifecycle-portfolio-piece
---

# Contract-to-Cash: Revenue Lifecycle Portfolio Piece

## Summary

A portfolio piece telling the full money-leak story for a $25M CPG brand — from gross contracted revenue through net cash received, showing where and how much evaporates at each stage. Differentiated from retailer-deduction-recovery by lifecycle breadth and Economist-style provocative headline framing. Specific narrative structure and visual approach emerge from data exploration.

---

## Problem Frame

The CEO of a $25M specialty food brand running SalesPad cannot answer: "On that national mass retailer deal we signed in Q1 — what did we actually net?" The answer lives in 6+ systems with different schemas, granularities, and time horizons. Nobody can trace contracted revenue through shipment, receiving, deductions, and payment to arrive at a net number.

This isn't a hypothetical. Brands at this scale ($20M–$50M) have outgrown their tools but haven't yet invested in systems that provide visibility. They tolerate the blind spot because they can't see its cost. The portfolio piece makes the cost visible — and makes CFOs recognize their own company.

The existing portfolio already covers deduction recovery (retailer-deduction-recovery) and short-ship costs (short-ship-cost). Neither tells the full lifecycle story. Neither answers "what did we actually net?" C2C is the piece that does.

---

## Actors

- A1. CFO (primary viewer): Sees the total gap, identifies blind spots, compares retailer performance. The person who forwards this to the CEO and says "this is us."
- A2. CEO (secondary viewer): Sees true profitability by retailer. Makes the call to engage.
- A3. Portfolio visitor (discovery): Lands on the piece from LinkedIn or search. Needs to understand the story in 30 seconds without context.

---

## Requirements

**Story and framing**

- R1. The piece tells a complete revenue lifecycle story — from gross contracted/invoiced revenue through net cash received — showing leakage at every material stage between
- R2. The framing uses an Economist-style provocative headline that immediately differentiates from retailer-deduction-recovery and signals "this is a bigger story"
- R3. The piece produces three reactions in sequence: (1) shock at the total gap, (2) discovery of specific blind-spot stages, (3) comparative insight across retailers
- R4. All written content uses Economist voice: sober, declarative, data-forward. No marketing language, no hedging that softens findings

**Data and integrity**

- R5. All figures reconcile with established Cinderhaven numbers: $25M revenue, 50 SKUs, 10 B2B retailers + DTC channel, 3,087 deductions, 5,838 B2B orders/shipments
- R6. When the lifecycle story requires data not currently in the platform, new synthetic data is generated that is additive and internally consistent with existing projects
- R7. Every claim or figure in the piece traces back to a verifiable query against the platform

**Visual and interaction**

- R8. One anchor visual delivers the headline's promise in a single look — a viewer grasps the core story without scrolling or clicking
- R9. Economist chart style: minimal decoration, no gratuitous interactivity, text labels on data, horizontal gridlines only, no 3D or gradients
- R10. The piece is a narrative, not a dashboard — it tells a story rather than providing an exploration tool
- R11. Supporting detail (stage breakdowns, retailer comparisons) is available but subordinate to the anchor visual

**Technical**

- R12. React SPA built with Vite, deployed to Cloudflare Pages
- R13. Data served as static JSON files, pre-aggregated from the platform via Python export script
- R14. Lailara Design System tokens applied (typography, color palette, layout)

**Discovery-driven process**

- R15. Narrative structure, visual approach, and interaction model are determined by data exploration — not prescribed before the data is understood
- R16. Data exploration must answer: what lifecycle stages exist in the data, what the total gross-to-net gap is, where the largest leakage points are, and which retailers show the most dramatic variation

---

## Acceptance Examples

- AE1. **Covers R1, R3, R8.** A CFO viewing the anchor visual can state within 10 seconds: the total revenue that entered the lifecycle, the net amount that arrived as cash, and the approximate size of the largest leakage category — without reading body text.
- AE2. **Covers R5, R7.** The total deduction figure shown in C2C matches the $1.53M total from retailer-deduction-recovery's summary.json when measured over the same time window.
- AE3. **Covers R2, R10.** A portfolio visitor who has just viewed retailer-deduction-recovery immediately perceives C2C as a different story (lifecycle breadth vs. single-stage depth) based on headline and anchor visual alone.

---

## Success Criteria

- A CFO at a $25M–$50M CPG brand sees their own company in this piece and can articulate what it would mean to have this visibility for their data
- The piece is immediately distinguishable from retailer-deduction-recovery in both framing and scope — no "why are there two deduction pieces?" confusion
- Every number in the piece can be traced to a specific query against the Cinderhaven platform
- The narrative is complete — a viewer understands the full story without needing to reference other portfolio pieces

---

## Scope Boundaries

### Deferred for later

- Specific headline text (emerges from data exploration)
- Specific chart type for the anchor visual (emerges from data exploration)
- Single-view vs. multi-section structure (emerges from data exploration)
- Interaction patterns beyond the anchor (determined after core narrative is solid)
- LinkedIn/marketing content derived from the piece

### Outside this product's identity

- Dashboard-style filtering and exploration (this is a narrative, not a tool)
- DE proof or technical showcase (the platform handles that)
- Jupyter notebook as a separate deliverable
- Individual PO tracing as a feature (unless data exploration reveals it's the compelling hook)
- Streamlit or any server-rendered application
- Extending the platform beyond what this specific story requires

---

## Key Decisions

- **Lifecycle breadth is the structural differentiator from RDR:** C2C covers the full revenue lifecycle; RDR covers one stage (deductions) in depth. This is the portfolio-level positioning.
- **Headline framing does the instant-differentiation work:** A viewer knows this is a different piece within 5 seconds because the headline promises a different story, not just different data.
- **Data exploration before design:** The narrative structure, visual approach, and format are outputs of understanding the data, not inputs to the build. This is a deliberate sequencing choice.
- **Narrative over tool:** This piece tells a story rather than providing an exploration interface. Supporting detail exists but is subordinate to the authored narrative.

---

## Dependencies / Assumptions

- Cinderhaven Data Platform is live with fct_orders, fct_shipments, fct_deductions, fct_payments, fct_chargebacks, dim_retailers, dim_products (verified)
- The platform data can support lifecycle-level joins or aggregations sufficient to tell a gross-to-net story (to be verified in data exploration)
- New synthetic data can be generated without breaking existing projects' validation suites
- The Lailara Design System is the visual standard for this piece

---

## Outstanding Questions

### Deferred to Planning

- [Affects R1, R16][Needs research] What lifecycle stages can actually be traced in the current platform data? What's the join path from orders → shipments → deductions → payments?
- [Affects R6][Needs research] What data gaps exist? Specifically: are contract terms, payment timing, and cash receipt dates present, or do they need to be synthesized?
- [Affects R8][Technical] What chart type best delivers a gross-to-net lifecycle story in a single view? (Sankey, waterfall, stacked bar, something else — depends on data shape)
- [Affects R5][Technical] What's the exact reconciliation surface between C2C and other Cinderhaven projects? Which figures must match exactly vs. which are derived differently?
