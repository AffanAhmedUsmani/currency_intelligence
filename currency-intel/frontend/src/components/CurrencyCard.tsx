import { AlertTriangle } from "lucide-react";
import type { CurrencyCard as CurrencyCardType } from "../types";
import { formatNumber, formatPct, formatRate, pctColorClass, volatilityLabel } from "../lib/format";
import { Sparkline } from "./Sparkline";

interface Props {
  card: CurrencyCardType;
  base: string;
  amount: number;
  onClick: () => void;
}

const VOLATILITY_DOT: Record<string, string> = {
  low: "bg-blue-500",
  normal: "bg-emerald-500",
  elevated: "bg-amber-500",
  high: "bg-rose-500",
  unknown: "bg-slate-400",
};

export function CurrencyCard({ card, base, amount, onClick }: Props) {
  const positive = (card.pct_change ?? 0) >= 0;
  const amountEquivalent = card.current_rate !== null ? amount * card.current_rate : null;

  return (
    <button
      onClick={onClick}
      className="group flex w-full flex-col rounded-2xl border bg-[var(--bg-elevated)] p-4 text-left transition-all hover:border-[var(--accent)] hover:shadow-md"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-2xl leading-none">{card.flag}</span>
          <div>
            <div className="font-semibold leading-tight">{card.code}</div>
            <div className="text-[11px] text-[var(--text-muted)] leading-tight truncate max-w-[110px]">{card.name}</div>
          </div>
        </div>
        {card.data_warning && (
          <span title={card.data_warning}>
            <AlertTriangle size={14} className="text-amber-500 mt-1" />
          </span>
        )}
      </div>

      <div className="mt-3 flex items-end justify-between">
        <div>
          <div className="text-xs text-[var(--text-muted)]">
            1 {base} = {formatRate(card.current_rate)} {card.code}
          </div>
          <div className={`text-lg font-semibold ${pctColorClass(card.pct_change)}`}>{formatPct(card.pct_change)}</div>
        </div>
        <div className="text-right">
          <div className="text-[11px] text-[var(--text-muted)]">{formatNumber(amount)} {base} ≈</div>
          <div className="text-sm font-semibold">
            {formatNumber(amountEquivalent)} {card.code}
          </div>
        </div>
      </div>

      <div className="mt-2">
        <Sparkline data={card.sparkline} positive={positive} />
      </div>

      <div className="mt-2 flex items-center gap-1.5 text-[11px] text-[var(--text-muted)]">
        <span className={`h-1.5 w-1.5 rounded-full ${VOLATILITY_DOT[card.volatility_classification] ?? VOLATILITY_DOT.unknown}`} />
        {volatilityLabel(card.volatility_classification)}
      </div>
    </button>
  );
}
