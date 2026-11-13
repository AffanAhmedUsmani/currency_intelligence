import { useMemo, useState } from "react";
import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { Brush, CartesianGrid, Line, ComposedChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { X } from "lucide-react";
import { TrendingDown, TrendingUp } from "lucide-react";
import { fetchAnalysis, postCalculator } from "../api/client";
import { formatNumber, formatPct, formatRate, pctColorClass, PERIOD_LABELS } from "../lib/format";
import { mergeForChart, seriesToRows } from "../lib/mergeSeries";
import { useAppStore } from "../store/useAppStore";
import { RecommendationBadge } from "./RecommendationBadge";
import { MiniLineChart } from "./MiniLineChart";
import { SimpleSelect } from "./SimpleSelect";
import type { CalculatorResponse, Period } from "../types";

interface Props {
  base: string;
  code: string;
  defaultPeriod: Period;
  onClose: () => void;
}

// Deliberately distinct from `var(--accent)` (the price line's color) so the
// SMA 30 overlay never visually merges with the raw price series.
const SMA_COLORS: Record<string, string> = {
  "7": "#f59e0b",
  "14": "#8b5cf6",
  "30": "#ec4899",
  "50": "#0d9f6e",
  "200": "#e0383f",
};

const TABS = ["Your Results", "Overview", "Chart & Indicators", "Volatility & Risk", "Mean Reversion", "Forecast", "Backtest"] as const;
type Tab = (typeof TABS)[number];

export function DetailModal({ base, code, defaultPeriod, onClose }: Props) {
  const amount = useAppStore((s) => s.amount);
  const globalFeePct = useAppStore((s) => s.feePct);
  const [period, setPeriod] = useState<Period>(defaultPeriod);
  const [tab, setTab] = useState<Tab>("Your Results");
  const [smaToggle, setSmaToggle] = useState<Record<string, boolean>>({ "30": true, "50": true, "200": false, "7": false, "14": false });
  const [showBollinger, setShowBollinger] = useState(false);

  // Optional: if the user has a real quote from a transfer provider (e.g. Western
  // Union) for this exact pair, use the spread THAT implies instead of the generic
  // nav-bar fee assumption — grounds the P/L projections in a rate they can
  // actually get rather than a guess.
  const [quotedRateInput, setQuotedRateInput] = useState("");

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["analysis", base, code, period],
    queryFn: () => fetchAnalysis(base, code, period),
  });

  const quotedRate = Number(quotedRateInput);
  const hasValidQuote = quotedRateInput.trim() !== "" && !Number.isNaN(quotedRate) && quotedRate > 0;
  const impliedSpreadPct =
    hasValidQuote && data?.latest_rate
      ? Math.max(0, ((data.latest_rate - quotedRate) / data.latest_rate) * 100)
      : null;
  const effectiveFeePct = impliedSpreadPct ?? globalFeePct;

  const calcQuery = useQuery({
    queryKey: ["calculator", base, code, amount, period, effectiveFeePct],
    queryFn: () =>
      postCalculator({ base, target: code, amount, fee_pct: effectiveFeePct, comparison_period: period }),
    enabled: tab === "Your Results",
  });

  const chartData = useMemo(() => {
    if (!data) return [];
    const overlays: Record<string, typeof data.chart.display> = {};
    Object.entries(data.indicators.sma).forEach(([w, series]) => {
      overlays[`sma${w}`] = series;
    });
    overlays.bb_upper = data.indicators.bollinger.upper;
    overlays.bb_lower = data.indicators.bollinger.lower;
    return mergeForChart(data.chart.display, overlays);
  }, [data]);

  const rsiData = useMemo(() => (data ? seriesToRows(data.indicators.rsi14).map((r) => ({ date: r.date, rsi: r.value })) : []), [data]);
  const macdData = useMemo(() => {
    if (!data) return [];
    return data.indicators.macd.line.map((p, i) => ({
      date: p.date,
      macd: p.value,
      signal: data.indicators.macd.signal[i]?.value ?? null,
      histogram: data.indicators.macd.histogram[i]?.value ?? null,
    }));
  }, [data]);
  const atrData = useMemo(() => (data ? seriesToRows(data.indicators.atr_proxy).map((r) => ({ date: r.date, atr: r.value })) : []), [data]);
  const stochData = useMemo(() => (data ? seriesToRows(data.indicators.stochastic_proxy).map((r) => ({ date: r.date, stoch: r.value })) : []), [data]);
  const volData = useMemo(() => {
    if (!data) return [];
    return data.volatility.ewma_annualized.map((p, i) => ({
      date: p.date,
      ewma: p.value !== null ? p.value * 100 : null,
      rolling: data.volatility.annualized[i]?.value !== null && data.volatility.annualized[i]?.value !== undefined ? (data.volatility.annualized[i].value as number) * 100 : null,
    }));
  }, [data]);

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-0 sm:p-6">
      <div className="min-h-screen w-full max-w-5xl rounded-none bg-[var(--bg)] sm:min-h-0 sm:rounded-2xl sm:border">
        <div className="sticky top-0 z-10 flex items-center justify-between border-b bg-[var(--bg)] px-5 py-4">
          <div className="flex items-center gap-3">
            <span className="text-3xl">{data?.flag ?? "🏳️"}</span>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold">{base}/{code}</h2>
                {data && <RecommendationBadge label={data.opportunity.classification} />}
              </div>
              <div className="text-xs text-[var(--text-muted)]">{data?.name}</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <SimpleSelect
              value={period}
              onChange={(v) => setPeriod(v as Period)}
              options={Object.entries(PERIOD_LABELS).map(([value, label]) => ({ value, label }))}
            />
            <button onClick={onClose} className="flex h-9 w-9 items-center justify-center rounded-xl border hover:border-[var(--accent)]">
              <X size={16} />
            </button>
          </div>
        </div>

        {isLoading && <div className="p-10 text-center text-[var(--text-muted)]">Loading detailed analysis…</div>}
        {isError && (
          <div className="p-10 text-center text-[var(--negative)]">
            Could not load analysis: {(error as Error)?.message ?? "Unknown error"}
          </div>
        )}

        {data && (
          <div className="px-5 py-4">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <div className="text-sm text-[var(--text-muted)]">1 {base} =</div>
                <div className="text-3xl font-bold">
                  {formatRate(data.latest_rate)} {code}
                </div>
                <div className={`text-sm font-medium ${pctColorClass(data.pct_change)}`}>
                  {formatPct(data.pct_change)} over {PERIOD_LABELS[period]}
                </div>
              </div>
              <div className="text-right text-xs text-[var(--text-muted)]">
                <div>Source: {data.provider} ({data.rate_kind} rate)</div>
                <div>{data.n_observations} observations used</div>
                {data.data_warning && <div className="text-amber-500">{data.data_warning}</div>}
              </div>
            </div>

            <div className="mt-4 flex gap-1 overflow-x-auto border-b">
              {TABS.map((t) => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className={`whitespace-nowrap px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
                    tab === t ? "border-[var(--accent)] text-[var(--accent)]" : "border-transparent text-[var(--text-muted)] hover:text-[var(--text)]"
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>

            <div className="py-4">
              {tab === "Your Results" && (
                <YourResultsTab
                  query={calcQuery}
                  amount={amount}
                  period={period}
                  quotedRateInput={quotedRateInput}
                  onQuotedRateChange={setQuotedRateInput}
                  impliedSpreadPct={impliedSpreadPct}
                  globalFeePct={globalFeePct}
                  currentRate={data?.latest_rate ?? null}
                  targetCode={code}
                  baseCode={base}
                />
              )}

              {tab === "Overview" && (
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="rounded-xl border bg-[var(--bg-elevated)] p-4">
                    <div className="text-xs text-[var(--text-muted)]">Opportunity Score</div>
                    <div className="text-3xl font-bold">{data.opportunity.score?.toFixed(0) ?? "—"}<span className="text-sm text-[var(--text-muted)]">/100</span></div>
                    <p className="mt-2 text-sm leading-relaxed">{data.opportunity.summary}</p>
                  </div>
                  <div className="rounded-xl border bg-[var(--bg-elevated)] p-4 text-sm space-y-2">
                    <Row label="Support (period low)" value={formatRate(data.support_estimate)} />
                    <Row label="Resistance (period high)" value={formatRate(data.resistance_estimate)} />
                    <Row label="Trend direction" value={data.trend.direction} />
                    <Row label="Momentum" value={data.trend.momentum_state.replaceAll("_", " ")} />
                    <Row label="Volatility regime" value={data.volatility.regime} />
                  </div>
                  <ListCard title="Supporting signals" items={data.opportunity.supporting_signals} tone="positive" />
                  <ListCard title="Contradicting signals" items={data.opportunity.contradicting_signals} tone="negative" />
                  <ListCard title="Risks" items={data.opportunity.risks} tone="neutral" />
                  <ListCard title="What would change this view" items={data.opportunity.invalidation_conditions} tone="neutral" />
                </div>
              )}

              {tab === "Chart & Indicators" && (
                <div className="space-y-5">
                  <div>
                    <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
                      {Object.keys(data.indicators.sma).map((w) => (
                        <label key={w} className="flex items-center gap-1 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={!!smaToggle[w]}
                            onChange={() => setSmaToggle((s) => ({ ...s, [w]: !s[w] }))}
                          />
                          <span style={{ color: SMA_COLORS[w] }}>SMA {w}</span>
                        </label>
                      ))}
                      <label className="flex items-center gap-1 cursor-pointer">
                        <input type="checkbox" checked={showBollinger} onChange={() => setShowBollinger((s) => !s)} />
                        Bollinger Bands
                      </label>
                    </div>
                    <ResponsiveContainer width="100%" height={320}>
                      <ComposedChart data={chartData} margin={{ top: 4, right: 10, bottom: 0, left: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                        <XAxis dataKey="date" tick={{ fontSize: 10, fill: "var(--text-muted)" }} minTickGap={50} />
                        <YAxis tick={{ fontSize: 10, fill: "var(--text-muted)" }} width={60} domain={["auto", "auto"]} />
                        <Tooltip contentStyle={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }} />
                        {showBollinger && (
                          <>
                            <Line type="monotone" dataKey="bb_upper" stroke="var(--text-muted)" strokeDasharray="3 3" dot={false} strokeWidth={1} isAnimationActive={false} connectNulls />
                            <Line type="monotone" dataKey="bb_lower" stroke="var(--text-muted)" strokeDasharray="3 3" dot={false} strokeWidth={1} isAnimationActive={false} connectNulls />
                          </>
                        )}
                        {Object.entries(smaToggle).filter(([, on]) => on).map(([w]) => (
                          <Line key={w} type="monotone" dataKey={`sma${w}`} stroke={SMA_COLORS[w]} dot={false} strokeWidth={1.5} isAnimationActive={false} connectNulls />
                        ))}
                        <Line type="monotone" dataKey="price" stroke="var(--accent)" strokeWidth={2} dot={false} isAnimationActive={false} />
                        <Brush dataKey="date" height={24} stroke="var(--accent)" travellerWidth={8} />
                      </ComposedChart>
                    </ResponsiveContainer>
                    <p className="mt-1 text-[11px] text-[var(--text-muted)]">Drag the handles below the chart to zoom into a date range.</p>
                  </div>

                  <IndicatorBlock title="RSI (14)" note="Below 30 = historically oversold. Above 70 = historically overbought.">
                    <MiniLineChart data={rsiData} series={[{ key: "rsi", color: "#8b5cf6", label: "RSI" }]} referenceLines={[{ y: 30, label: "30" }, { y: 70, label: "70" }]} yDomain={[0, 100]} />
                  </IndicatorBlock>

                  <IndicatorBlock title="MACD" note="Crossovers between the MACD line and signal line are classic trend-change signals.">
                    <MiniLineChart data={macdData} series={[{ key: "macd", color: "#2563eb", label: "MACD" }, { key: "signal", color: "#e0383f", label: "Signal" }]} />
                  </IndicatorBlock>

                  <div className="grid gap-4 sm:grid-cols-2">
                    <IndicatorBlock title="ATR proxy" note="Close-to-close range proxy (no intraday high/low data available).">
                      <MiniLineChart data={atrData} series={[{ key: "atr", color: "#f59e0b", label: "ATR proxy" }]} />
                    </IndicatorBlock>
                    <IndicatorBlock title="Stochastic proxy" note="Position of the close within its recent range (0-100).">
                      <MiniLineChart data={stochData} series={[{ key: "stoch", color: "#0d9f6e", label: "%K proxy" }]} yDomain={[0, 100]} />
                    </IndicatorBlock>
                  </div>
                </div>
              )}

              {tab === "Volatility & Risk" && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <Stat label="Volatility regime" value={data.volatility.regime} />
                    <Stat label="Volatility percentile" value={data.volatility.percentile !== null ? `${data.volatility.percentile.toFixed(0)}th` : "—"} />
                    <Stat label="Max drawdown" value={formatPct(data.volatility.max_drawdown_pct)} />
                    <Stat label="Downside deviation" value={data.volatility.downside_deviation_pct !== null ? `${formatNumber(data.volatility.downside_deviation_pct)}%` : "—"} />
                  </div>
                  <IndicatorBlock title="Annualized volatility" note="Rolling window vs. EWMA (reacts faster to recent shocks) — both annualized.">
                    <MiniLineChart data={volData} series={[{ key: "rolling", color: "#2563eb", label: "Rolling" }, { key: "ewma", color: "#e0383f", label: "EWMA" }]} />
                  </IndicatorBlock>
                  <p className="text-sm text-[var(--text-muted)]">
                    A falling exchange rate is not the same as a safe one to buy — this section measures how large and
                    erratic recent moves have been, independent of direction.
                  </p>
                </div>
              )}

              {tab === "Mean Reversion" && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <Stat label="Z-score vs. own average" value={data.mean_reversion.zscore !== null ? data.mean_reversion.zscore.toFixed(2) : "—"} />
                    <Stat label="Bollinger position" value={data.mean_reversion.bollinger_position !== null ? data.mean_reversion.bollinger_position.toFixed(2) : "—"} />
                    <Stat label="AR(1) coefficient" value={data.mean_reversion.ar1_coefficient !== null ? data.mean_reversion.ar1_coefficient.toFixed(2) : "—"} />
                    <Stat label="Half-life (days)" value={data.mean_reversion.half_life_days !== null ? data.mean_reversion.half_life_days.toFixed(0) : "—"} />
                  </div>
                  <div className={`rounded-xl border p-4 text-sm ${data.mean_reversion.is_statistically_supported ? "border-emerald-500/40 bg-emerald-500/5" : "border-amber-500/40 bg-amber-500/5"}`}>
                    {data.mean_reversion.note}
                  </div>
                </div>
              )}

              {tab === "Forecast" && (
                <div className="space-y-4">
                  {data.forecast.confidence === "insufficient_data" ? (
                    <div className="rounded-xl border p-4 text-sm text-[var(--text-muted)]">Insufficient data for a responsible forecast on this pair/period.</div>
                  ) : (
                    <>
                      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                        <Stat label="Horizon" value={`${data.forecast.horizon_days} days`} />
                        <Stat label="Expected move (median)" value={formatPct(data.forecast.expected_pct_move)} />
                        <Stat label="Probability of appreciation" value={`${data.forecast.prob_appreciation?.toFixed(0)}%`} />
                        <Stat label="Confidence" value={data.forecast.confidence} />
                      </div>
                      <div className="rounded-xl border bg-[var(--bg-elevated)] p-4">
                        <div className="text-xs text-[var(--text-muted)] mb-1">90% plausible range of outcomes</div>
                        <div className="text-lg font-semibold">
                          {formatPct(data.forecast.ci_low_pct)} to {formatPct(data.forecast.ci_high_pct)}
                        </div>
                      </div>
                    </>
                  )}
                  <p className="text-sm text-[var(--text-muted)]">{data.forecast.note}</p>
                </div>
              )}

              {tab === "Backtest" && (
                <div className="space-y-4">
                  {!data.backtest ? (
                    <div className="rounded-xl border p-4 text-sm text-[var(--text-muted)]">Not enough history for a meaningful backtest on this pair.</div>
                  ) : (
                    <>
                      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                        <Stat label="Signals found" value={String(data.backtest.n_signals)} />
                        <Stat label="Signal hit rate" value={data.backtest.signal_hit_rate_pct !== null ? `${data.backtest.signal_hit_rate_pct.toFixed(0)}%` : "—"} />
                        <Stat label="Baseline hit rate" value={`${data.backtest.baseline_hit_rate_pct?.toFixed(0)}%`} />
                        <Stat label="Beats baseline?" value={data.backtest.beats_baseline === null ? "—" : data.backtest.beats_baseline ? "Yes" : "No"} />
                      </div>
                      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                        <Stat label="Avg return after signal" value={formatPct(data.backtest.avg_signal_return_pct)} />
                        <Stat label="Avg baseline return" value={formatPct(data.backtest.avg_baseline_return_pct)} />
                        <Stat label="Worst move after signal" value={formatPct(data.backtest.max_adverse_move_pct)} />
                      </div>
                      <p className="text-sm text-[var(--text-muted)]">{data.backtest.note}</p>
                    </>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-[var(--text-muted)]">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border bg-[var(--bg-elevated)] p-3">
      <div className="text-[11px] text-[var(--text-muted)]">{label}</div>
      <div className="font-semibold capitalize">{value}</div>
    </div>
  );
}

function ListCard({ title, items, tone }: { title: string; items: string[]; tone: "positive" | "negative" | "neutral" }) {
  const toneColor = tone === "positive" ? "text-emerald-600 dark:text-emerald-400" : tone === "negative" ? "text-rose-600 dark:text-rose-400" : "text-[var(--text-muted)]";
  return (
    <div className="rounded-xl border bg-[var(--bg-elevated)] p-4">
      <div className={`text-sm font-semibold mb-2 ${toneColor}`}>{title}</div>
      {items.length === 0 ? (
        <div className="text-sm text-[var(--text-muted)]">None identified.</div>
      ) : (
        <ul className="space-y-1.5 text-sm list-disc pl-4">
          {items.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function YourResultsTab({
  query, amount, period, quotedRateInput, onQuotedRateChange, impliedSpreadPct, globalFeePct, currentRate, targetCode, baseCode,
}: {
  query: UseQueryResult<CalculatorResponse>;
  amount: number;
  period: Period;
  quotedRateInput: string;
  onQuotedRateChange: (v: string) => void;
  impliedSpreadPct: number | null;
  globalFeePct: number;
  currentRate: number | null;
  targetCode: string;
  baseCode: string;
}) {
  const { data, isLoading, isError, error } = query;

  const quoteBox = (
    <div className="rounded-xl border bg-[var(--bg-elevated)] p-3 text-sm">
      <label className="mb-1 block text-xs font-medium text-[var(--text-muted)]">
        Got a real quote from a transfer provider (e.g. Western Union) for 1 {baseCode} → {targetCode}? Enter it to
        ground these numbers in a rate you can actually get, instead of the {globalFeePct}% nav-bar estimate.
      </label>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-[var(--text-muted)]">1 {baseCode} =</span>
        <input
          type="number"
          step="any"
          value={quotedRateInput}
          onChange={(e) => onQuotedRateChange(e.target.value)}
          placeholder={currentRate ? currentRate.toFixed(6) : "0.0036"}
          className="w-32 rounded-lg border bg-[var(--bg-elevated)] px-2 py-1 text-sm outline-none focus:border-[var(--accent)]"
        />
        <span className="text-xs text-[var(--text-muted)]">{targetCode}</span>
        {impliedSpreadPct !== null && (
          <span className="ml-2 inline-flex items-center rounded-full bg-amber-500/10 px-2.5 py-1 text-xs font-medium text-amber-600 dark:text-amber-400">
            Implied spread: {impliedSpreadPct.toFixed(2)}% vs. our reference rate
          </span>
        )}
      </div>
      {impliedSpreadPct !== null && (
        <p className="mt-1 text-[11px] text-[var(--text-muted)]">
          Using this spread (not the nav-bar's {globalFeePct}%) for every number below, applied each way you'd
          convert. This is one real quote compared to an indicative mid-market rate — actual provider spreads vary
          by amount, payout method, and day.
        </p>
      )}
    </div>
  );

  if (isLoading) {
    return (
      <div className="space-y-4">
        {quoteBox}
        <div className="py-6 text-center text-sm text-[var(--text-muted)]">Calculating your results…</div>
      </div>
    );
  }
  if (isError) {
    return (
      <div className="space-y-4">
        {quoteBox}
        <p className="py-6 text-center text-sm text-[var(--negative)]">{(error as Error)?.message ?? "Could not calculate this."}</p>
      </div>
    );
  }
  if (!data) return null;

  const headline =
    data.holding_period_projections.find((p) => p.period === period) ?? data.holding_period_projections[0];
  const headlineIsLoss = headline && (headline.expected_profit_loss ?? 0) < 0;
  const headlineHasData = headline && headline.confidence !== "insufficient_data" && headline.expected_profit_loss !== null;

  return (
    <div className="space-y-4">
      {quoteBox}

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-xs text-[var(--text-muted)]">
            {formatNumber(amount)} {data.base} would buy you approximately
          </div>
          <div className="text-3xl font-bold">
            {formatNumber(data.received_amount)} {data.target}
          </div>
          <div className="text-xs text-[var(--text-muted)]">
            at 1 {data.base} = {formatRate(data.current_rate)} {data.target} ({data.rate_kind}), after a{" "}
            {formatNumber(data.fee_cost_in_base_currency)} {data.base} fee ({data.fee_pct}%
            {impliedSpreadPct !== null ? " — your quoted spread" : " — nav-bar transfer fee"})
          </div>
        </div>
        <RecommendationBadge label={data.decision_support.recommendation} />
      </div>

      {headlineHasData && (
        <div
          className={`flex flex-wrap items-center justify-between gap-3 rounded-xl border p-3 ${
            headlineIsLoss ? "border-rose-500/30 bg-rose-500/5" : "border-emerald-500/30 bg-emerald-500/5"
          }`}
        >
          <div className="flex items-center gap-2">
            {headlineIsLoss ? (
              <TrendingDown size={18} className="text-rose-500" />
            ) : (
              <TrendingUp size={18} className="text-emerald-500" />
            )}
            <div>
              <div className={`text-xs font-bold uppercase tracking-wide ${headlineIsLoss ? "text-rose-500" : "text-emerald-500"}`}>
                {headlineIsLoss ? "Projected loss" : "Projected profit"}
                {headline!.period !== period && ` (${PERIOD_LABELS[headline!.period] ?? headline!.period} basis)`}
              </div>
              <div className={`text-xl font-bold ${headlineIsLoss ? "text-rose-500" : "text-emerald-500"}`}>
                {(headline!.expected_profit_loss ?? 0) >= 0 ? "+" : ""}
                {formatNumber(headline!.expected_profit_loss)} {data.base}
                <span className="ml-1 text-sm font-medium">({formatPct(headline!.expected_profit_loss_pct)})</span>
              </div>
            </div>
          </div>
          <div className="text-right text-xs text-[var(--text-muted)]">
            <div>if you hold {data.target} for {PERIOD_LABELS[headline!.period] ?? headline!.period}, then convert back</div>
            <div>
              you'd end up with <strong className="text-[var(--text)]">{formatNumber(headline!.expected_value)} {data.base}</strong> on average
              {" "}({headline!.prob_profit_pct?.toFixed(0)}% chance of a profit)
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Stat label={`${PERIOD_LABELS[data.historical.period]} change`} value={formatPct(data.historical.pct_change)} />
        <Stat label="Period high / low" value={`${formatRate(data.historical.period_high)} / ${formatRate(data.historical.period_low)}`} />
        <Stat label="Period average" value={formatRate(data.historical.period_avg)} />
      </div>

      <div>
        <div className="mb-2 text-sm font-semibold">If you convert now and hold {data.target}…</div>
        {data.holding_period_projections[0]?.confidence === "insufficient_data" ? (
          <div className="rounded-xl border p-3 text-sm text-[var(--text-muted)]">
            Not enough historical data for this pair to project holding-period outcomes.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-xl border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-black/5 dark:bg-white/5 text-left text-[11px] text-[var(--text-muted)]">
                  <th className="px-3 py-2 font-medium">Holding period</th>
                  <th className="px-3 py-2 font-medium">Projected result</th>
                  <th className="px-3 py-2 font-medium">Pessimistic → Optimistic</th>
                  <th className="px-3 py-2 font-medium">Prob. of profit</th>
                </tr>
              </thead>
              <tbody>
                {data.holding_period_projections.map((p) => {
                  const pl = p.expected_profit_loss ?? 0;
                  const loss = pl < 0;
                  return (
                    <tr key={p.period} className="border-b last:border-b-0">
                      <td className="px-3 py-2 font-medium">{PERIOD_LABELS[p.period] ?? p.period}</td>
                      <td className="px-3 py-2">
                        <div className={`flex items-center gap-1.5 font-semibold ${loss ? "text-rose-500" : "text-emerald-500"}`}>
                          {loss ? <TrendingDown size={14} /> : <TrendingUp size={14} />}
                          {loss ? "Loss" : "Profit"}: {pl >= 0 ? "+" : ""}
                          {formatNumber(pl)} {data.base} ({formatPct(p.expected_profit_loss_pct)})
                        </div>
                      </td>
                      <td className="px-3 py-2 text-[var(--text-muted)]">
                        {formatNumber(p.pessimistic_profit_loss)} → +{formatNumber(p.optimistic_profit_loss)}
                      </td>
                      <td className="px-3 py-2">{p.prob_profit_pct?.toFixed(0)}%</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div>
        <div className="mb-2 text-sm font-semibold">If you wait to convert instead</div>
        <div className="grid gap-2 sm:grid-cols-2">
          {data.scenarios.map((s, i) => (
            <div key={i} className="rounded-xl border p-3 text-sm">
              <div className="text-[var(--text-muted)] text-xs">{s.label}</div>
              <div className="font-semibold">
                {formatNumber(s.received_amount)} {data.target}
                <span className={`ml-2 text-xs ${(s.diff_vs_current ?? 0) >= 0 ? "text-emerald-500" : "text-rose-500"}`}>
                  ({(s.diff_vs_current ?? 0) >= 0 ? "+" : ""}{formatNumber(s.diff_vs_current)})
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-xl border bg-amber-500/5 border-amber-500/30 p-3 text-sm">
        {data.decision_support.explanation}
      </div>
      <p className="text-[11px] text-[var(--text-muted)]">
        Assumes a {data.fee_pct}% {impliedSpreadPct !== null ? "quoted" : "transfer provider"} spread each way.{" "}
        {data.disclaimer}
      </p>
    </div>
  );
}

function IndicatorBlock({ title, note, children }: { title: string; note: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border bg-[var(--bg-elevated)] p-4">
      <div className="mb-1 text-sm font-semibold">{title}</div>
      <div className="mb-2 text-[11px] text-[var(--text-muted)]">{note}</div>
      {children}
    </div>
  );
}
