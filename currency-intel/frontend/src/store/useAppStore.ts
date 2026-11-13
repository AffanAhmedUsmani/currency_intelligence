import { create } from "zustand";
import type { Period } from "../types";

type Theme = "light" | "dark";

function initialTheme(): Theme {
  try {
    const saved = localStorage.getItem("ci-theme");
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    /* ignore */
  }
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

interface AppState {
  theme: Theme;
  toggleTheme: () => void;

  // Committed inputs — these drive every query. "Committed" (vs. a draft
  // input state) so typing in the amount field doesn't refetch on every
  // keystroke; the nav bar's Analyze button (or Enter) commits a change.
  base: string;
  amount: number;
  chartPeriod: Period;
  // Round-trip transfer cost assumed everywhere P/L is projected (the calculator,
  // the basket, the strategy backtest) — modeling a real transfer provider's spread
  // (e.g. Western Union-style), not just an abstract fee. Global so every view's
  // "transactional accountability" is consistent, not silently using different
  // assumptions in different places.
  feePct: number;
  setBase: (base: string) => void;
  setAmount: (amount: number) => void;
  setChartPeriod: (period: Period) => void;
  setFeePct: (feePct: number) => void;

  selectedCode: string | null;
  openDetail: (code: string) => void;
  closeDetail: () => void;
}

export const useAppStore = create<AppState>((set, get) => ({
  theme: initialTheme(),
  toggleTheme: () => {
    const next = get().theme === "dark" ? "light" : "dark";
    try {
      localStorage.setItem("ci-theme", next);
    } catch {
      /* ignore */
    }
    set({ theme: next });
  },

  base: "PKR",
  amount: 200000,
  chartPeriod: "3m",
  feePct: 1.5,
  setBase: (base) => set({ base }),
  setAmount: (amount) => set({ amount }),
  setChartPeriod: (chartPeriod) => set({ chartPeriod }),
  setFeePct: (feePct) => set({ feePct }),

  selectedCode: null,
  openDetail: (code) => set({ selectedCode: code }),
  closeDetail: () => set({ selectedCode: null }),
}));
