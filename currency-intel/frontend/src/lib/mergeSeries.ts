import type { SeriesPoint } from "../types";

export function toMap(points: SeriesPoint[] | undefined): Map<string, number | null> {
  const m = new Map<string, number | null>();
  (points ?? []).forEach((p) => m.set(p.date, p.value));
  return m;
}

/** Builds one row per date in `base`, attaching each named overlay's value
 * (looked up by date) so a single chart can plot price + indicators that
 * were computed over a longer history than what's displayed. */
export function mergeForChart(
  base: SeriesPoint[],
  overlays: Record<string, SeriesPoint[] | undefined>
): Record<string, number | string | null>[] {
  const overlayMaps = Object.fromEntries(Object.entries(overlays).map(([k, v]) => [k, toMap(v)]));
  return base.map((p) => {
    const row: Record<string, number | string | null> = { date: p.date, price: p.value };
    for (const key of Object.keys(overlayMaps)) {
      row[key] = overlayMaps[key].get(p.date) ?? null;
    }
    return row;
  });
}

export function seriesToRows(points: SeriesPoint[] | undefined): { date: string; value: number | null }[] {
  return (points ?? []).map((p) => ({ date: p.date, value: p.value }));
}
