import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchCompare, fetchCurrencies } from "./api/client";
import { useAppStore } from "./store/useAppStore";
import { Header } from "./components/Header";
import { BestFiveBasket, TOP_N } from "./components/BestFiveBasket";
import { CurrencyChartsGrid } from "./components/CurrencyChartsGrid";
import { DetailModal } from "./components/DetailModal";
import { StrategyBacktest } from "./components/StrategyBacktest";

export default function App() {
  const { base, amount, chartPeriod, feePct, theme, selectedCode, openDetail, closeDetail } = useAppStore();

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

  const currenciesQuery = useQuery({ queryKey: ["currencies"], queryFn: fetchCurrencies });

  const compareQuery = useQuery({
    queryKey: ["compare", base, chartPeriod],
    queryFn: () => fetchCompare(base, chartPeriod, "majors"),
  });

  const currencies = currenciesQuery.data?.currencies ?? [];

  return (
    <div className="min-h-screen pb-16">
      <Header
        currencies={currencies}
        isLoading={compareQuery.isFetching}
        lastUpdated={compareQuery.data?.last_updated ?? null}
      />

      <main className="mx-auto max-w-7xl space-y-8 px-4 py-6 sm:px-6">
        <BestFiveBasket base={base} amount={amount} feePct={feePct} />
        <StrategyBacktest base={base} topN={TOP_N} defaultFeePct={feePct} />

        {compareQuery.isLoading && (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="h-44 animate-pulse rounded-2xl border bg-[var(--bg-elevated)]" />
            ))}
          </div>
        )}

        {compareQuery.isError && (
          <div className="rounded-2xl border border-rose-500/40 bg-rose-500/5 p-6 text-rose-500">
            Could not load currency charts: {(compareQuery.error as Error)?.message}. The data provider may be
            temporarily unavailable — try again in a moment.
          </div>
        )}

        {compareQuery.data && (
          <CurrencyChartsGrid cards={compareQuery.data.cards} base={base} amount={amount} onSelect={openDetail} />
        )}

        <footer className="pt-4 text-center text-[11px] text-[var(--text-muted)]">
          Rates are daily reference/indicative data (Frankfurter/ECB and Yahoo Finance FX crosses), not executable
          dealer quotes. Historical performance does not guarantee future results — this tool supports decisions, it
          does not make them for you.
        </footer>
      </main>

      {selectedCode && (
        <DetailModal base={base} code={selectedCode} defaultPeriod={chartPeriod} onClose={closeDetail} />
      )}
    </div>
  );
}
