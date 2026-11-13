import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Shield, TrendingDown, TrendingUp } from "lucide-react";
import { fetchOpportunities, postPortfolioOptimize } from "../api/client";
import { formatNumber, formatPct, PERIOD_LABELS } from "../lib/format";
import type { Period, PortfolioResponse } from "../types";

interface Props {
  base: string;
  amount: number;
  feePct: number;
}

export const TOP_N = 3;
const HOLDING_PERIODS: Period[] = ["7d", "14d", "1m", "3m", "6m", "1y"];

type RiskTier = "low" | "medium" | "high";

const RISK_TIERS: { value: RiskTier; label: string; hint: string }[] = [
  { value: "low", label: "Low risk", hint: "Safest split (minimum-variance)" },
  { value: "medium", label: "Medium risk", hint: "Balanced between safety and growth" },
  { value: "high", label: "High risk", hint: "More weight on the highest-return pick" },
];

// Keyed by the user's chosen tier (not the backend's absolute volatility bucket) so the badge
// always agrees with whichever Low/Medium/High button is selected — an absolute Low/Moderate/
// High/Very High bucket calibrated for ~1-month+ horizons was misleadingly almost always "Low"
// for a 1-week hold even at the High-risk setting, since a week just can't accumulate much
// volatility in absolute terms. The real, horizon-specific volatility number is still shown.
const RISK_TIER_COLORS: Record<RiskTier, string> = {
  low: "text-emerald-500 bg-emerald-500/10",
  medium: "text-amber-500 bg-amber-500/10",
  high: "text-rose-500 bg-rose-500/10",
};

export function BestFiveBasket({ base, amount, feePct }: Props) {
  const [period, setPeriod] = useState<Period>("1m");
  const [riskTier, setRiskTier] = useState<RiskTier>("low");

  // Ranked using the SAME holding period the basket targets — a currency's buying
  // signal over 1 month can differ a lot from its signal over 1 year, so picking the
  // "best N" once at a fixed period and reusing it for every tab understated how good
  // (or poor) a basket could be for longer/shorter horizons.
  const topQuery = useQuery({
    queryKey: ["best-n", base, period, TOP_N],
    queryFn: () => fetchOpportunities(base, period, TOP_N),
  });

  const targets = topQuery.data?.top_opportunities.map((c) => c.code) ?? [];
  const targetsKey = targets.join(",");

  // Always fetch the safest (minimum-variance) split first — it's the "Low risk" tier directly,
  // and it also tells us the achievable return range needed to compute "Medium"/"High" targets.
  const baselineQuery = useQuery({
    queryKey: ["best-n-baseline", base, amount, period, targetsKey, feePct],
    queryFn: () =>
      postPortfolioOptimize({
        base, targets, amount, fee_pct: feePct, holding_period: period, target_return_pct: null,
      }),
    enabled: targets.length >= 2,
  });

  const tieredTarget = useMemo(() => {
    if (riskTier === "low" || !baselineQuery.data) return null;
    const safe = baselineQuery.data.effective_target_return_pct;
    const max = baselineQuery.data.achievable_return_max_pct;
    const fraction = riskTier === "medium" ? 0.5 : 0.85; // "high" stops short of the single-currency corner
    return safe + fraction * (max - safe);
  }, [riskTier, baselineQuery.data]);

  const tieredQuery = useQuery({
    queryKey: ["best-n-tiered", base, amount, period, targetsKey, riskTier, tieredTarget?.toFixed(3), feePct],
    queryFn: () =>
      postPortfolioOptimize({
        base, targets, amount, fee_pct: feePct, holding_period: period, target_return_pct: tieredTarget,
      }),
    enabled: riskTier !== "low" && tieredTarget !== null,
  });

  const data: PortfolioResponse | undefined = riskTier === "low" ? baselineQuery.data : tieredQuery.data;
  const isLoading = topQuery.isLoading || baselineQuery.isLoading || (riskTier !== "low" && tieredQuery.isLoading);
  const isError = topQuery.isError || baselineQuery.isError || (riskTier !== "low" && tieredQuery.isError);
  const error = topQuery.error ?? baselineQuery.error ?? tieredQuery.error;

  const isLoss = data ? data.outcome.expected_profit_loss < 0 : false;

  return (
    <section className="rounded-2xl border bg-[var(--bg-elevated)] p-5">
      <div className="mb-1 flex items-center gap-2">
        <Shield size={18} className="text-[var(--accent)]" />
        <h2 className="text-lg font-semibold">Best {TOP_N} currencies to invest in right now</h2>
      </div>
      <p className="mb-4 text-[12px] text-[var(--text-muted)]">
        Automatically picks the {TOP_N} currencies with the strongest buying signal against {base} and splits your{" "}
        {formatNumber(amount)} {base} across them so that if one underperforms, the others can offset it. Pick a
        holding period and a risk level to see how the split and expected outcome change.
      </p>

      <div className="mb-3 flex gap-1 overflow-x-auto border-b">
        {HOLDING_PERIODS.map((p) => (
          <button
            key={p}
            onClick={() => setPeriod(p)}
            className={`whitespace-nowrap px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              period === p
                ? "border-[var(--accent)] text-[var(--accent)]"
                : "border-transparent text-[var(--text-muted)] hover:text-[var(--text)]"
            }`}
          >
            {PERIOD_LABELS[p]}
          </button>
        ))}
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        {RISK_TIERS.map((t) => (
          <button
            key={t.value}
            onClick={() => setRiskTier(t.value)}
            title={t.hint}
            className={`rounded-xl border px-3 py-1.5 text-sm font-medium transition-colors ${
              riskTier === t.value
                ? "border-[var(--accent)] bg-[var(--accent)]/10 text-[var(--accent)]"
                : "text-[var(--text-muted)] hover:border-[var(--accent)]"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {isLoading && (
        <div className="text-sm text-[var(--text-muted)]">Finding the best currencies and building a basket…</div>
      )}
      {isError && (
        <p className="text-sm text-[var(--negative)]">{(error as Error)?.message ?? "Could not build a basket right now."}</p>
      )}

      {data && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <span className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-semibold ${RISK_TIER_COLORS[riskTier]}`}>
              {RISK_TIERS.find((t) => t.value === riskTier)?.label} · {data.analytic_volatility_pct.toFixed(1)}% volatility over {PERIOD_LABELS[period]}
            </span>
            <span className="text-sm text-[var(--text-muted)]">
              Targeting {formatPct(data.effective_target_return_pct)} over {PERIOD_LABELS[period]}
            </span>
          </div>

          <div
            className={`flex flex-wrap items-center justify-between gap-3 rounded-xl border p-3 ${
              isLoss ? "border-rose-500/30 bg-rose-500/5" : "border-emerald-500/30 bg-emerald-500/5"
            }`}
          >
            <div className="flex items-center gap-2">
              {isLoss ? (
                <TrendingDown size={18} className="text-rose-500" />
              ) : (
                <TrendingUp size={18} className="text-emerald-500" />
              )}
              <div>
                <div className={`text-xs font-bold uppercase tracking-wide ${isLoss ? "text-rose-500" : "text-emerald-500"}`}>
                  {isLoss ? "Projected loss" : "Projected profit"} (expected)
                </div>
                <div className={`text-xl font-bold ${isLoss ? "text-rose-500" : "text-emerald-500"}`}>
                  {data.outcome.expected_profit_loss >= 0 ? "+" : ""}
                  {formatNumber(data.outcome.expected_profit_loss)} {data.base}
                  <span className="ml-1 text-sm font-medium">({formatPct(data.outcome.expected_profit_loss_pct)})</span>
                </div>
              </div>
            </div>
            <div className="text-right text-xs text-[var(--text-muted)]">
              <div>on {formatNumber(amount)} {data.base} invested</div>
              <div>
                you'd end up with <strong className="text-[var(--text)]">{formatNumber(data.outcome.expected_value)} {data.base}</strong> on average
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-3">
              <TrendingUp size={18} className="shrink-0 text-emerald-500" />
              <div>
                <div className="text-xs font-bold uppercase tracking-wide text-emerald-500">Projected profit (best case)</div>
                <div className="text-lg font-bold text-emerald-500">
                  +{formatNumber(data.outcome.optimistic_profit_loss)} {data.base}
                  <span className="ml-1 text-sm font-medium">
                    ({formatPct((data.outcome.optimistic_profit_loss / data.amount) * 100)})
                  </span>
                </div>
                <div className="text-[11px] text-[var(--text-muted)]">
                  ends at {formatNumber(data.outcome.optimistic_value)} {data.base}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2 rounded-xl border border-rose-500/30 bg-rose-500/5 p-3">
              <TrendingDown size={18} className="shrink-0 text-rose-500" />
              <div>
                <div className="text-xs font-bold uppercase tracking-wide text-rose-500">Projected loss (worst case)</div>
                <div className="text-lg font-bold text-rose-500">
                  {formatNumber(data.outcome.pessimistic_profit_loss)} {data.base}
                  <span className="ml-1 text-sm font-medium">
                    ({formatPct((data.outcome.pessimistic_profit_loss / data.amount) * 100)})
                  </span>
                </div>
                <div className="text-[11px] text-[var(--text-muted)]">
                  ends at {formatNumber(data.outcome.pessimistic_value)} {data.base}
                </div>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Stat label="Probability of profit" value={`${data.outcome.prob_profit_pct.toFixed(0)}%`} />
          </div>

          <div>
            <div className="mb-2 text-sm font-semibold">How to split it</div>
            <div className="overflow-x-auto rounded-xl border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-black/5 dark:bg-white/5 text-left text-[11px] text-[var(--text-muted)]">
                    <th className="px-3 py-2 font-medium">Currency</th>
                    <th className="px-3 py-2 font-medium">Buy</th>
                    <th className="px-3 py-2 font-medium">Share</th>
                    <th className="px-3 py-2 font-medium">Its own expected return</th>
                    <th className="px-3 py-2 font-medium">Its own volatility</th>
                  </tr>
                </thead>
                <tbody>
                  {data.allocation.map((a) => (
                    <tr key={a.code} className="border-b last:border-b-0">
                      <td className="px-3 py-2 font-medium">
                        <span className="mr-1">{a.flag}</span>
                        {a.code}
                      </td>
                      <td className="px-3 py-2 font-semibold">
                        {formatNumber(a.amount)} {data.base}
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex items-center gap-2">
                          <div className="h-1.5 w-16 overflow-hidden rounded-full bg-black/10 dark:bg-white/10">
                            <div className="h-full bg-[var(--accent)]" style={{ width: `${Math.min(100, a.weight_pct)}%` }} />
                          </div>
                          {a.weight_pct.toFixed(1)}%
                        </div>
                      </td>
                      <td className={`px-3 py-2 ${a.individual_expected_return_pct >= 0 ? "text-emerald-500" : "text-rose-500"}`}>
                        {formatPct(a.individual_expected_return_pct)}
                      </td>
                      <td className="px-3 py-2 text-[var(--text-muted)]">{formatPct(a.individual_volatility_pct)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {riskTier !== "high" && (
            <div className="flex items-start gap-2 rounded-xl border bg-black/5 dark:bg-white/5 p-3 text-xs">
              <TrendingUp size={15} className="mt-0.5 shrink-0 text-[var(--accent)]" />
              <p>
                Want more upside? Switching to <strong>{riskTier === "low" ? "Medium" : "High"} risk</strong> above
                targets more expected return (up to <strong>{formatPct(data.achievable_return_max_pct)}</strong> at
                the High setting) in exchange for higher volatility — more expected profit always comes with more
                risk here, never for free.
              </p>
            </div>
          )}

          {data.correlation_warnings.length > 0 && (
            <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-3 text-xs space-y-1">
              {data.correlation_warnings.map((w, i) => (
                <p key={i}>⚠ {w}</p>
              ))}
            </div>
          )}

          <p className="text-[11px] text-[var(--text-muted)]">
            Assumes a {feePct}% transfer provider spread each way (set in the nav bar). {data.note}
          </p>
        </div>
      )}
    </section>
  );
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="rounded-xl border p-3">
      <div className="text-[11px] text-[var(--text-muted)]">{label}</div>
      <div className={`font-semibold ${color ?? ""}`}>{value}</div>
    </div>
  );
}
