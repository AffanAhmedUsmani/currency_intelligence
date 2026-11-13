import { useState } from "react";
import { Moon, Sun, TrendingUp } from "lucide-react";
import { useAppStore } from "../store/useAppStore";
import { CurrencySelect } from "./CurrencySelect";
import type { CurrencyMeta } from "../types";

interface Props {
  currencies: CurrencyMeta[];
  isLoading: boolean;
  lastUpdated: string | null;
}

export function Header({ currencies, isLoading, lastUpdated }: Props) {
  const { base, amount, feePct, setBase, setAmount, setFeePct, theme, toggleTheme } = useAppStore();
  const [draftAmount, setDraftAmount] = useState(String(amount));
  const [draftFeePct, setDraftFeePct] = useState(String(feePct));

  function commitAmount() {
    const parsed = Number(draftAmount);
    if (!Number.isNaN(parsed) && parsed > 0) setAmount(parsed);
    else setDraftAmount(String(amount));
  }

  function commitFeePct() {
    const parsed = Number(draftFeePct);
    if (!Number.isNaN(parsed) && parsed >= 0) setFeePct(parsed);
    else setDraftFeePct(String(feePct));
  }

  return (
    <header className="sticky top-0 z-30 border-b bg-[var(--bg)]/90 backdrop-blur-md">
      <div className="mx-auto max-w-7xl px-4 py-3 sm:px-6">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 mr-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--accent)] text-white">
              <TrendingUp size={18} />
            </div>
            <div>
              <div className="font-semibold leading-tight">Currency Intelligence</div>
              <div className="text-[11px] text-[var(--text-muted)] leading-tight">Where should I put my money?</div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-[var(--text-muted)]">I have</span>
              <CurrencySelect currencies={currencies} value={base} onChange={setBase} />
            </div>

            <input
              type="number"
              value={draftAmount}
              onChange={(e) => setDraftAmount(e.target.value)}
              onBlur={commitAmount}
              onKeyDown={(e) => e.key === "Enter" && commitAmount()}
              className="w-32 rounded-xl border bg-[var(--bg-elevated)] px-3 py-2 text-sm outline-none focus:border-[var(--accent)]"
              aria-label="Amount"
            />

            <div className="flex items-center gap-1.5" title="The round-trip cost a real transfer provider (e.g. Western Union) would charge — used everywhere profit/loss is projected, not just an abstract fee.">
              <span className="text-xs text-[var(--text-muted)]">Transfer fee</span>
              <input
                type="number"
                step="0.1"
                min={0}
                value={draftFeePct}
                onChange={(e) => setDraftFeePct(e.target.value)}
                onBlur={commitFeePct}
                onKeyDown={(e) => e.key === "Enter" && commitFeePct()}
                className="w-16 rounded-xl border bg-[var(--bg-elevated)] px-3 py-2 text-sm outline-none focus:border-[var(--accent)]"
                aria-label="Transfer fee percent"
              />
              <span className="text-xs text-[var(--text-muted)]">%</span>
            </div>

            <button
              onClick={commitAmount}
              disabled={isLoading}
              className="rounded-xl bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white shadow-sm transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {isLoading ? "Analyzing…" : "Analyze"}
            </button>
          </div>

          <div className="ml-auto flex items-center gap-3">
            {lastUpdated && (
              <span className="hidden sm:inline text-xs text-[var(--text-muted)]">
                Updated {new Date(lastUpdated).toLocaleTimeString()}
              </span>
            )}
            <button
              onClick={toggleTheme}
              aria-label="Toggle theme"
              className="flex h-9 w-9 items-center justify-center rounded-xl border hover:border-[var(--accent)] transition-colors"
            >
              {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
