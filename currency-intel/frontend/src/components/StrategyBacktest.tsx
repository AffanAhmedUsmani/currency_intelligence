import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronUp, FlaskConical } from "lucide-react";
import { fetchWeeklyRotationBacktest } from "../api/client";
import { formatNumber, formatPct, PERIOD_LABELS } from "../lib/format";
import { SimpleSelect } from "./SimpleSelect";
import type { Period } from "../types";

interface Props {
  base: string;
  topN: number;
  defaultFeePct: number;
}

const REBALANCE_OPTIONS: { value: Period; days: number }[] = [
  { value: "7d", days: 7 },
  { value: "14d", days: 14 },
  { value: "1m", days: 30 },
  { value: "3m", days: 90 },
  { value: "6m", days: 182 },
];

export function StrategyBacktest({ base, topN, defaultFeePct }: Props) {
  const [open, setOpen] = useState(false);
  const [rebalance, setRebalance] = useState<Period>("7d");
  // Starts from the nav bar's global transfer-fee setting, but stays independently
  // adjustable here — this panel is specifically for fee-sensitivity exploration
  // ("how much of this result is just transaction cost"), not just a mirror of it.
  const [feePct, setFeePct] = useState(defaultFeePct);

  const rebalanceDays = REBALANCE_OPTIONS.find((o) => o.value === rebalance)?.days ?? 7;

  const query = useQuery({
    queryKey: ["weekly-rotation-backtest", base, topN, rebalanceDays, feePct],
    queryFn: () =>
      fetchWeeklyRotationBacktest({ base, universe: "majors", top_n: topN, rebalance_days: rebalanceDays, fee_pct: feePct }),
    enabled: open,
  });

  const data = query.data;

  // Pure mechanical fee drag over the same number of rebalances, with zero price
  // movement — isolates "how much of this is just transaction costs" from "how much
  // is the trading signal actually losing/winning", shown so that's never hidden
  // inside a single cumulative-return number.
  const feeDragOnlyPct = data
    ? (Math.pow((1 - feePct / 100) ** 2, data.n_checkpoints) - 1) * 100
    : null;

  return (
    <section className="rounded-2xl border bg-[var(--bg-elevated)] p-5">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-2 text-left"
      >
        <div className="flex items-center gap-2">
          <FlaskConical size={18} className="text-[var(--accent)]" />
          <div>
            <h2 className="text-lg font-semibold">How reliable is this, historically?</h2>
            <p className="text-[12px] text-[var(--text-muted)]">
              A walk-forward backtest of actually rotating into the top picks on a schedule — not just a claim.
            </p>
          </div>
        </div>
        {open ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
      </button>

      {open && (
        <div className="mt-4 space-y-4 border-t pt-4">
          <p className="text-[12px] text-[var(--text-muted)]">
            Simulates rotating into the top {topN} statistically cheapest currencies (by the same valuation
            z-score this app's scoring is built on) every rebalance period, over real historical data, and
            compares it to simply diversifying across every candidate every period. This tests the core{" "}
            <em>selection</em> signal with equal weighting — not the live mean-variance-optimized basket, and
            not the full 8-component opportunity score (which would be too slow to re-run at every historical
            checkpoint). Treat it as validating the foundation the live picks are built on, not the exact
            live numbers.
          </p>

          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="mb-1 block text-xs text-[var(--text-muted)]">Rotate every</label>
              <SimpleSelect
                value={rebalance}
                onChange={(v) => setRebalance(v as Period)}
                options={REBALANCE_OPTIONS.map((o) => ({ value: o.value, label: PERIOD_LABELS[o.value] }))}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-[var(--text-muted)]">Round-trip fee per rotation (%)</label>
              <input
                type="number"
                step="0.1"
                min={0}
                value={feePct}
                onChange={(e) => setFeePct(Number(e.target.value))}
                className="w-28 rounded-xl border bg-[var(--bg-elevated)] px-3 py-2 text-sm outline-none focus:border-[var(--accent)]"
              />
            </div>
          </div>

          {query.isLoading && <div className="text-sm text-[var(--text-muted)]">Running the backtest…</div>}
          {query.isError && (
            <p className="text-sm text-[var(--negative)]">{(query.error as Error)?.message ?? "Could not run the backtest."}</p>
          )}

          {data && (
            <>
              {data.n_checkpoints === 0 ? (
                <div className="rounded-xl border p-3 text-sm text-[var(--text-muted)]">{data.note}</div>
              ) : (
                <div className="space-y-4">
                  <div
                    className={`rounded-xl border p-3 text-sm font-medium ${
                      data.beats_benchmark
                        ? "border-emerald-500/30 bg-emerald-500/5 text-emerald-500"
                        : "border-rose-500/30 bg-rose-500/5 text-rose-500"
                    }`}
                  >
                    {data.beats_benchmark ? "✓ " : "✗ "}
                    {data.beats_benchmark
                      ? "This selection beat simply diversifying across every candidate, historically."
                      : "This selection did NOT beat simply diversifying across every candidate, historically."}
                  </div>

                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <Stat
                      label="Strategy cumulative"
                      value={formatPct(data.strategy_cumulative_return_pct)}
                      color={data.strategy_cumulative_return_pct >= 0 ? "text-emerald-500" : "text-rose-500"}
                    />
                    <Stat label="Benchmark cumulative" value={formatPct(data.benchmark_cumulative_return_pct)} />
                    <Stat label="Win rate" value={`${data.strategy_win_rate_pct.toFixed(0)}%`} />
                    <Stat label="Worst drawdown" value={formatPct(data.strategy_max_drawdown_pct)} color="text-rose-500" />
                  </div>

                  {feeDragOnlyPct !== null && feePct > 0 && (
                    <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-3 text-xs">
                      <strong>Fee impact check:</strong> rebalancing {data.n_checkpoints} times at {feePct}%
                      round-trip cost alone — with zero price movement — would already cost{" "}
                      <strong>{formatPct(feeDragOnlyPct)}</strong> cumulatively. The strategy's actual result above
                      ({formatPct(data.strategy_cumulative_return_pct)}) includes that same drag, so compare the two:
                      the closer they are, the more the result is being driven by fees rather than by the trading
                      signal itself. At {PERIOD_LABELS[rebalance]} rebalancing, frequent round-trips can make fees
                      the dominant factor even when the underlying signal has a real, measurable edge.
                    </div>
                  )}

                  <div>
                    <div className="mb-2 text-sm font-semibold">Most frequently selected</div>
                    <div className="flex flex-wrap gap-2">
                      {data.selection_frequency.slice(0, 8).map((s) => (
                        <span key={s.code} className="inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs">
                          {s.flag} {s.code} · {s.pct_of_periods.toFixed(0)}%
                        </span>
                      ))}
                    </div>
                  </div>

                  <p className="text-[11px] text-[var(--text-muted)]">
                    {data.n_checkpoints} rebalance periods tested across {data.n_candidates} candidate currencies
                    ({formatNumber(data.n_candidates - data.excluded_codes.length)} with enough history). {data.note}
                  </p>
                </div>
              )}
            </>
          )}
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
