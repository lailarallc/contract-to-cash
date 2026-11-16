import { useEffect, useState } from "react";
import { loadData, type AppData } from "./data";
import { WaterfallChart } from "./components/WaterfallChart";
import { RetailerChart } from "./components/RetailerChart";
import { TimeToCashChart } from "./components/TimeToCashChart";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { formatDollars } from "./chartConstants";
import "./styles.css";

export function App() {
  const [data, setData] = useState<AppData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadData().then(setData).catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="error">Failed to load data: {error}</div>;
  if (!data) return <div className="loading">Loading...</div>;

  const { summary, lifecycle, retailers } = data;

  // Itemized deductions carry real records (count > 0). The gross-to-net
  // residual (count === 0) is an unreconciled shortfall — largely un-itemized
  // trade spend — NOT an itemized deduction, so it is reported separately and
  // never counted as a "deduction category."
  const itemizedStages = lifecycle.b2b.stages.filter((s) => (s.count ?? 0) > 0);
  const residualStage = lifecycle.b2b.stages.find((s) => (s.count ?? 0) === 0);
  const itemizedCount = itemizedStages.length;
  const itemizedTotal = itemizedStages.reduce((sum, s) => sum + s.amount, 0);
  const residualTotal = residualStage?.amount ?? 0;
  const totalShortfall = lifecycle.b2b.gross - lifecycle.b2b.net;

  const retailerCount = retailers.leakage.length;
  const leakagePcts = retailers.leakage.map((r) => r.leakage_pct);
  const minLeakage = leakagePcts.length > 0 ? Math.min(...leakagePcts) : 0;
  const maxLeakage = leakagePcts.length > 0 ? Math.max(...leakagePcts) : 0;
  const leakageSpread = (maxLeakage - minLeakage).toFixed(1);

  // Derive the leakage-vs-size relationship from the data instead of asserting
  // it: in the shipped data the LARGEST partner has the HIGHEST rate.
  const byGrossDesc = [...retailers.leakage].sort((a, b) => b.gross - a.gross);
  const byLeakageDesc = [...retailers.leakage].sort((a, b) => b.leakage_pct - a.leakage_pct);
  const largestRetailer = byGrossDesc[0];
  const worstLeakageRetailer = byLeakageDesc[0];
  const largestIsWorst =
    !!largestRetailer && !!worstLeakageRetailer &&
    largestRetailer.name === worstLeakageRetailer.name;

  const sortedByDays = [...retailers.time_to_cash].sort(
    (a, b) => a.avg_days - b.avg_days,
  );
  const fastest = sortedByDays[0] ?? { name: "N/A", avg_days: 0 };
  const slowest = sortedByDays[sortedByDays.length - 1] ?? { name: "N/A", avg_days: 0 };
  const daySpread = Math.round(slowest.avg_days - fastest.avg_days);

  const ttc = retailers.time_to_cash_meta;

  return (
    <main className="page">
      <header className="hero">
        <div className="brand">
          <span className="brand-name">Cinderhaven Provisions</span>
          <span className="brand-sub">Revenue Lifecycle Analysis &middot; {summary.meta.time_window}</span>
        </div>
        <h1 className="headline">{summary.headline}</h1>
        <p className="subhead">
          Of {formatDollars(summary.combined.total_invoiced)} invoiced across{" "}
          {summary.meta.retailers_b2b} retail partners and a DTC channel over{" "}
          {summary.meta.time_window}, only {formatDollars(summary.combined.total_net)}{" "}
          arrived as cash. The rest evaporated in trade allowances, operational
          deductions, chargebacks, and a payment-timing residual.
        </p>
        <div className="stat-row">
          <div className="stat-card">
            <span className="stat-value">
              {summary.combined.cents_per_dollar}&cent;
            </span>
            <span className="stat-label">per dollar invoiced</span>
          </div>
          <div className="stat-card">
            <span className="stat-value">{summary.b2b.leakage_pct}%</span>
            <span className="stat-label">B2B leakage rate</span>
          </div>
          <div className="stat-card">
            <span className="stat-value">{summary.dtc.leakage_pct}%</span>
            <span className="stat-label">DTC leakage rate</span>
          </div>
        </div>
      </header>

      <ErrorBoundary section="waterfall">
        <section className="section" id="waterfall">
          <h2 className="section-title">
            {formatDollars(totalShortfall)} Separates Gross Payments from Cash — Only {formatDollars(itemizedTotal)} Is Itemized
          </h2>
          <p className="section-body">
            Of {formatDollars(lifecycle.b2b.gross)} in gross B2B payments acknowledged
            by retailers, only {formatDollars(lifecycle.b2b.net)} arrived as cash.
            {" "}{formatDollars(itemizedTotal)} is itemized across {itemizedCount} deduction
            categories — from post-audit claims to short-ship penalties. The remaining
            {" "}{formatDollars(residualTotal)} is an unreconciled gross-to-net shortfall
            (largely un-itemized trade spend), shown separately because it is not tied
            to a deduction record.
          </p>
          <div className="chart-container" role="img" aria-label={`Waterfall chart showing gross payments of ${formatDollars(lifecycle.b2b.gross)} declining through ${itemizedCount} itemized deduction categories and an unreconciled residual to net received of ${formatDollars(lifecycle.b2b.net)}`}>
            <WaterfallChart lifecycle={lifecycle} />
          </div>
          <p className="footnote">
            Source: fct_retailer_payments, fct_retailer_deductions. Gross = sum of
            remittance gross_amount across {summary.b2b.remittance_count} remittances.
            Net = gross minus itemized deductions and the unreconciled residual.
            {" "}{summary.meta.time_window}.
          </p>
        </section>
      </ErrorBoundary>

      <ErrorBoundary section="retailers">
        <section className="section" id="retailers">
          <h2 className="section-title">
            A {leakageSpread}-Point Gap Separates the Best and Worst Retailers
          </h2>
          <p className="section-body">
            Leakage rates range from {minLeakage}% to {maxLeakage}% — a{" "}
            {leakageSpread} percentage-point spread across {retailerCount} direct
            retail partners.{" "}
            {largestIsWorst
              ? `The largest partner by dollar flow (${largestRetailer.name}) carries the highest leakage rate (${worstLeakageRetailer.leakage_pct}%) — scale brings more scrutiny, not less.`
              : `${worstLeakageRetailer?.name ?? "The top partner"} carries the highest leakage rate (${worstLeakageRetailer?.leakage_pct ?? maxLeakage}%).`}
          </p>
          <div className="chart-container" role="img" aria-label={`Horizontal bar chart comparing leakage rates across ${retailerCount} retailers, ranging from ${minLeakage}% to ${maxLeakage}%`}>
            <RetailerChart retailers={retailers.leakage} />
          </div>
          <p className="footnote">
            Source: fct_payments grouped by retailer_name. Leakage % = (gross -
            net) / gross. {summary.meta.time_window}.
          </p>
        </section>
      </ErrorBoundary>

      <ErrorBoundary section="timing">
        <section className="section" id="timing">
          <h2 className="section-title">
            {daySpread} Days Separate the Fastest and Slowest Payer
          </h2>
          <p className="section-body">
            Beyond what is deducted, the speed of payment varies dramatically.
            The fastest payer ({fastest.name}) averages {Math.round(fastest.avg_days)} days
            to cash while the slowest ({slowest.name}) takes {Math.round(slowest.avg_days)}.
            That {daySpread}-day spread is working capital locked in transit — invisible
            on the P&L but real in cash flow.
          </p>
          <div className="chart-container" role="img" aria-label={`Horizontal bar chart showing average days to cash by retailer, from ${Math.round(fastest.avg_days)} days for ${fastest.name} to ${Math.round(slowest.avg_days)} days for ${slowest.name}`}>
            <TimeToCashChart timeToCash={retailers.time_to_cash} />
          </div>
          <p className="footnote">
            Source: fct_retailer_orders.po_date to fct_retailer_payments.received_date,
            measured once per order (first payment) from the purchase-order date.
            Time to cash for the {ttc.covered_orders.toLocaleString()} orders with a
            recorded payment ({ttc.coverage_pct}% of all{" "}
            {ttc.total_orders.toLocaleString()} orders); the rest have no linked
            payment in this dataset. Payments carry no order_id, so a deduction is
            the only order-to-payment link.
            {" "}{summary.meta.time_window}.
          </p>
        </section>
      </ErrorBoundary>

      <footer className="footer">
        <p>
          Source: Cinderhaven Data Platform (synthetic demonstration data).{" "}
          {summary.meta.time_window}.{" "}
          {summary.b2b.deduction_count.toLocaleString()} itemized deductions across{" "}
          {summary.meta.orders_b2b.toLocaleString()} B2B orders and{" "}
          {summary.meta.orders_dtc.toLocaleString()} DTC orders.
        </p>
      </footer>
    </main>
  );
}
