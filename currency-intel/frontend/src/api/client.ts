import type {
  CalculatorResponse,
  CompareResponse,
  CurrencyMeta,
  DetailedAnalysis,
  Period,
  PortfolioResponse,
  Universe,
  WeeklyRotationBacktestResponse,
} from "../types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail || `Request failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function fetchCurrencies(): Promise<{ currencies: CurrencyMeta[]; default_majors: string[] }> {
  return request("/api/currencies");
}

export async function fetchCompare(
  base: string,
  period: Period,
  universe: Universe,
  limit = 20
): Promise<CompareResponse> {
  const params = new URLSearchParams({ base, period, universe, limit: String(limit) });
  return request(`/api/compare?${params.toString()}`);
}

export async function fetchOpportunities(base: string, period: Period, topN = 5) {
  const params = new URLSearchParams({ base, period, top_n: String(topN) });
  return request<{ base: string; period: string; top_opportunities: CompareResponse["cards"] }>(
    `/api/opportunities?${params.toString()}`
  );
}

export async function fetchAnalysis(base: string, target: string, period: Period): Promise<DetailedAnalysis> {
  return request(`/api/analysis/${base}/${target}?period=${period}`);
}

export async function postCalculator(payload: {
  base: string;
  target: string;
  amount: number;
  fee_pct: number;
  comparison_period: Period;
}): Promise<CalculatorResponse> {
  return request("/api/calculator", { method: "POST", body: JSON.stringify(payload) });
}

export async function postPortfolioOptimize(payload: {
  base: string;
  targets: string[];
  amount: number;
  fee_pct: number;
  holding_period: Period;
  target_return_pct: number | null;
}): Promise<PortfolioResponse> {
  return request("/api/portfolio/optimize", { method: "POST", body: JSON.stringify(payload) });
}

export async function fetchWeeklyRotationBacktest(params: {
  base: string;
  universe: Universe;
  top_n: number;
  rebalance_days: number;
  fee_pct: number;
}): Promise<WeeklyRotationBacktestResponse> {
  const qs = new URLSearchParams({
    base: params.base,
    universe: params.universe,
    top_n: String(params.top_n),
    rebalance_days: String(params.rebalance_days),
    fee_pct: String(params.fee_pct),
  });
  return request(`/api/backtest/weekly-rotation?${qs.toString()}`);
}
