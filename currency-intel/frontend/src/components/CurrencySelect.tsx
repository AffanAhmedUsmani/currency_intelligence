import { useMemo, useRef, useState } from "react";
import { ChevronDown, Search } from "lucide-react";
import type { CurrencyMeta } from "../types";

interface Props {
  currencies: CurrencyMeta[];
  value: string;
  onChange: (code: string) => void;
}

export function CurrencySelect({ currencies, value, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);

  const selected = currencies.find((c) => c.code === value);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return currencies;
    return currencies.filter((c) => c.code.toLowerCase().includes(q) || c.name.toLowerCase().includes(q));
  }, [currencies, query]);

  function close() {
    setOpen(false);
    setQuery("");
  }

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded-xl border px-3 py-2 text-sm font-medium bg-[var(--bg-elevated)] hover:border-[var(--accent)] transition-colors min-w-[150px]"
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="text-lg leading-none">{selected?.flag ?? "🏳️"}</span>
        <span className="flex-1 text-left">{selected ? `${selected.code}` : "Select currency"}</span>
        <ChevronDown size={16} className="opacity-60" />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={close} />
          <div className="absolute z-50 mt-2 w-72 rounded-xl border bg-[var(--bg-elevated)] shadow-xl overflow-hidden">
            <div className="flex items-center gap-2 border-b px-3 py-2">
              <Search size={15} className="opacity-50" />
              <input
                autoFocus
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search currency or code..."
                className="flex-1 bg-transparent outline-none text-sm py-1"
              />
            </div>
            <div className="max-h-72 overflow-y-auto py-1">
              {filtered.length === 0 && (
                <div className="px-3 py-3 text-sm text-[var(--text-muted)]">No currencies match.</div>
              )}
              {filtered.map((c) => (
                <button
                  key={c.code}
                  onClick={() => {
                    onChange(c.code);
                    close();
                  }}
                  className={`flex w-full items-center gap-3 px-3 py-2 text-sm hover:bg-black/5 dark:hover:bg-white/5 ${
                    c.code === value ? "bg-[var(--accent)]/10" : ""
                  }`}
                >
                  <span className="text-lg leading-none">{c.flag}</span>
                  <span className="font-medium">{c.code}</span>
                  <span className="text-[var(--text-muted)] truncate">{c.name}</span>
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
