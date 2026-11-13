export interface CurrencyMeta {
  code: string;
  name: string;
  flag: string;
  liquidity_tier: number;
}

export type Period = "24h" | "7d" | "14d" | "1m" | "3m" | "6m" | "1y" | "2y" | "5y";
export type Universe = "majors" | "volatile" | "strongest" | "weakest" | "all";

export interface CurrencyCard {
  code: string;
  name: string;
  flag: string;
  current_rate: number | null;
  pct_change: number | null;
  abs_change: number | null;
  sparkline: (number | null)[];
  volatility_classification: "low" | "normal" | "elevated" | "high" | "unknown";
  volatility_percentile: number | null;
  momentum_classification: string;
  trend_direction: string;
  reversal_signal: string | null;
  opportunity_score: number | null;
  recommendation: string;
  recommendation_summary: string;
  provider: string;
  rate_kind: "reference" | "indicative";
  data_warning: string | null;
}

export interface MarketSummaryPick {
  code: string;
  name: string;
  flag: string;
}

export interface MarketSummary {
  best_buying_opportunity: MarketSummaryPick | null;
  strongest_performer: MarketSummaryPick | null;
  biggest_decline: MarketSummaryPick | null;
  highest_volatility: MarketSummaryPick | null;
  most_stable: MarketSummaryPick | null;
  strongest_momentum: MarketSummaryPick | null;
  possible_trend_reversal: MarketSummaryPick | null;
}

export interface CompareResponse {
  base: string;
  period: string;
  universe: string;
  last_updated: string;
  count: number;
  summary: MarketSummary;
  cards: CurrencyCard[];
}

export interface SeriesPoint {
  date: string;
  value: number | null;
}

export interface DetailedAnalysis {
  code: string;
  base: string;
  name: string;
  flag: string;
  latest_rate: number | null;
  pct_change: number | null;
  abs_change: number | null;
  provider: string;
  rate_kind: string;
  data_warning: string | null;
  n_observations: number;
  chart: { display: SeriesPoint[]; full_history: SeriesPoint[] };
  indicators: {
    sma: Record<string, SeriesPoint[]>;
    ema20: SeriesPoint[];
    rsi14: SeriesPoint[];
    macd: { line: SeriesPoint[]; signal: SeriesPoint[]; histogram: SeriesPoint[] };
    bollinger: { mid: SeriesPoint[]; upper: SeriesPoint[]; lower: SeriesPoint[] };
    roc: SeriesPoint[];
    momentum: SeriesPoint[];
    atr_proxy: SeriesPoint[];
    stochastic_proxy: SeriesPoint[];
    note: string;
  };
  volatility: {
    annualized: SeriesPoint[];
    ewma_annualized: SeriesPoint[];
    percentile: number | null;
    regime: string;
    max_drawdown_pct: number | null;
    downside_deviation_pct: number | null;
  };
  mean_reversion: {
    zscore: number | null;
    bollinger_position: number | null;
    ar1_coefficient: number | null;
    half_life_days: number | null;
    is_statistically_supported: boolean;
    note: string;
  };
  trend: {
    direction: string;
    momentum_state: string;
    reversal_signal: string | null;
    short_vs_long_pct: number | null;
  };
  forecast: {
    horizon_days: number | null;
    expected_pct_move: number | null;
    prob_appreciation: number | null;
    prob_depreciation: number | null;
    ci_low_pct: number | null;
    ci_high_pct: number | null;
    secondary_trend_pct: number | null;
    method: string | null;
    confidence: string;
    note: string;
  };
  support_estimate: number | null;
  resistance_estimate: number | null;
  opportunity: {
    score: number | null;
    classification: string;
    components: Record<string, number | null>;
    supporting_signals: string[];
    contradicting_signals: string[];
    risks: string[];
    invalidation_conditions: string[];
    summary: string;
  };
  backtest: {
    horizon_days: number;
    z_window: number;
    entry_threshold: number;
    n_signals: number;
    n_baseline_days: number;
    signal_hit_rate_pct: number | null;
    baseline_hit_rate_pct: number | null;
    avg_signal_return_pct: number | null;
    avg_baseline_return_pct: number | null;
    max_adverse_move_pct: number | null;
    brier_score: number | null;
    beats_baseline: boolean | null;
    note: string;
  } | null;
}

export interface PortfolioAllocationEntry {
  code: string;
  name: string;
  flag: string;
  weight_pct: number;
  amount: number;
  individual_expected_return_pct: number;
  individual_volatility_pct: number;
  provider: string | null;
}

export interface PortfolioResponse {
  base: string;
  holding_period: string;
  horizon_days: number;
  n_common_days: number;
  amount: number;
  fee_pct: number;
  excluded_codes: string[];
  achievable_return_min_pct: number;
  achievable_return_max_pct: number;
  requested_target_return_pct: number | null;
  effective_target_return_pct: number;
  was_clamped: boolean;
  analytic_volatility_pct: number;
  risk_level: "Low" | "Moderate" | "High" | "Very High";
  allocation: PortfolioAllocationEntry[];
  min_risk_portfolio: { weights_pct: Record<string, number>; expected_return_pct: number; volatility_pct: number };
  max_return_portfolio: { weights_pct: Record<string, number>; expected_return_pct: number; volatility_pct: number };
  outcome: {
    expected_value: number;
    expected_profit_loss: number;
    expected_profit_loss_pct: number;
    optimistic_value: number;
    optimistic_profit_loss: number;
    pessimistic_value: number;
    pessimistic_profit_loss: number;
    prob_profit_pct: number;
  };
  correlation_warnings: string[];
  note: string;
}

export interface WeeklyRotationSelectionFrequency {
  code: string;
  name: string;
  flag: string;
  times_selected: number;
  pct_of_periods: number;
}

export interface WeeklyRotationPeriod {
  date: string;
  selected: string[];
  strategy_return_pct: number;
  benchmark_return_pct: number;
}

export interface WeeklyRotationBacktestResponse {
  base: string;
  universe: string;
  top_n: number;
  rebalance_days: number;
  zscore_window: number;
  fee_pct: number;
  n_candidates: number;
  n_checkpoints: number;
  excluded_codes: string[];
  strategy_cumulative_return_pct: number;
  benchmark_cumulative_return_pct: number;
  strategy_annualized_return_pct: number | null;
  benchmark_annualized_return_pct: number | null;
  strategy_win_rate_pct: number;
  benchmark_win_rate_pct: number;
  strategy_avg_period_return_pct: number;
  strategy_period_return_std_pct: number;
  strategy_sharpe_like: number | null;
  strategy_max_drawdown_pct: number;
  beats_benchmark: boolean;
  selection_frequency: WeeklyRotationSelectionFrequency[];
  periods: WeeklyRotationPeriod[];
  note: string;
}

export interface CalculatorResponse {
  base: string;
  target: string;
  amount: number;
  fee_pct: number;
  current_rate: number | null;
  rate_kind: string;
  provider: string;
  received_amount: number | null;
  fee_cost_in_base_currency: number | null;
  historical: { period: string; pct_change: number | null; period_high: number; period_low: number; period_avg: number };
  scenarios: { label: string; rate: number | null; received_amount: number | null; diff_vs_current: number | null }[];
  holding_period_projections: {
    period: string;
    horizon_days: number;
    expected_value: number | null;
    expected_profit_loss: number | null;
    expected_profit_loss_pct: number | null;
    optimistic_value: number | null;
    optimistic_profit_loss: number | null;
    pessimistic_value: number | null;
    pessimistic_profit_loss: number | null;
    prob_profit_pct: number | null;
    confidence: string;
    note: string;
  }[];
  decision_support: {
    is_relatively_expensive_vs_history: boolean;
    has_recently_become_cheaper: boolean;
    decline_losing_or_gaining_speed: string;
    showing_signs_of_recovery: boolean;
    elevated_risk_of_further_moves: boolean;
    recommendation: string;
    explanation: string;
  };
  last_updated: string;
  disclaimer: string;
}
