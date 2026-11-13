import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import type { CurrencyCard as CurrencyCardType } from "../types";
import { CurrencyCard } from "./CurrencyCard";

interface Props {
  cards: CurrencyCardType[];
  base: string;
  amount: number;
  onSelect: (code: string) => void;
}

export function CurrencyChartsGrid({ cards, base, amount, onSelect }: Props) {
  const [query, setQuery] = useState("");

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return cards;
    return cards.filter((c) => c.code.toLowerCase().includes(q) || c.name.toLowerCase().includes(q));
  }, [cards, query]);

  return (
    <section>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">All currencies</h2>
        <div className="flex items-center gap-2 rounded-xl border bg-[var(--bg-elevated)] px-3 py-2">
          <Search size={14} className="opacity-50" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search..."
            className="w-32 bg-transparent text-sm outline-none"
          />
        </div>
      </div>

      {visible.length === 0 ? (
        <div className="rounded-xl border bg-[var(--bg-elevated)] p-8 text-center text-[var(--text-muted)]">
          No currencies match your search.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {visible.map((card) => (
            <CurrencyCard key={card.code} card={card} base={base} amount={amount} onClick={() => onSelect(card.code)} />
          ))}
        </div>
      )}
    </section>
  );
}
