export function formatRate(value: number | null | undefined, maxDigits = 6): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const abs = Math.abs(value);
  const digits = abs >= 100 ? 2 : abs >= 1 ? 4 : maxDigits;
  return value.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: 2 });
}

export function formatPct(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}%`;
}

export function formatNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toLocaleString(undefined, { maximumFractionDigits: digits });
}

export const RECOMMENDATION_STYLES: Record<string, { bg: string; fg: string; dot: string }> = {
  "STRONG BUY OPPORTUNITY": { bg: "bg-emerald-500/15", fg: "text-emerald-600 dark:text-emerald-400", dot: "bg-emerald-500" },
  "POTENTIAL BUY": { bg: "bg-emerald-500/10", fg: "text-emerald-600 dark:text-emerald-400", dot: "bg-emerald-400" },
  "WAIT / MONITOR": { bg: "bg-amber-500/10", fg: "text-amber-600 dark:text-amber-400", dot: "bg-amber-500" },
  "HOLD / NEUTRAL": { bg: "bg-slate-500/10", fg: "text-slate-600 dark:text-slate-300", dot: "bg-slate-400" },
  "AVOID FOR NOW": { bg: "bg-rose-500/10", fg: "text-rose-600 dark:text-rose-400", dot: "bg-rose-500" },
};

export function pctColorClass(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "text-slate-400";
  if (value > 0.05) return "text-emerald-600 dark:text-emerald-400";
  if (value < -0.05) return "text-rose-600 dark:text-rose-400";
  return "text-slate-400";
}

const VOLATILITY_LABELS: Record<string, string> = {
  low: "Low volatility",
  normal: "Normal volatility",
  elevated: "Elevated volatility",
  high: "High volatility",
  unknown: "Volatility unknown",
};

export function volatilityLabel(regime: string): string {
  return VOLATILITY_LABELS[regime] ?? regime;
}

const MOMENTUM_LABELS: Record<string, string> = {
  accelerating_up: "Gaining strength",
  decelerating_up: "Rise slowing down",
  flat: "Flat momentum",
  decelerating_down: "Decline losing speed",
  accelerating_down: "Decline speeding up",
  unknown: "Momentum unclear",
};

export function momentumLabel(state: string): string {
  return MOMENTUM_LABELS[state] ?? state;
}

const TREND_LABELS: Record<string, string> = {
  uptrend: "Uptrend",
  downtrend: "Downtrend",
  sideways: "Sideways",
  unknown: "Unclear",
};

export function trendLabel(direction: string): string {
  return TREND_LABELS[direction] ?? direction;
}

export const PERIOD_LABELS: Record<string, string> = {
  "24h": "24 Hours",
  "7d": "7 Days",
  "14d": "14 Days",
  "1m": "1 Month",
  "3m": "3 Months",
  "6m": "6 Months",
  "1y": "1 Year",
  "2y": "2 Years",
  "5y": "5 Years",
};

export const UNIVERSE_LABELS: Record<string, string> = {
  majors: "Major Global Currencies",
  volatile: "Top 20 Most Volatile",
  strongest: "Top 20 Strongest Performers",
  weakest: "Top 20 Weakest Performers",
  all: "All Supported Currencies",
};
