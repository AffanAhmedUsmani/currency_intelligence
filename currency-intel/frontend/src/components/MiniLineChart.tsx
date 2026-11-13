import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

interface SeriesDef {
  key: string;
  color: string;
  label: string;
}

interface Props {
  data: Record<string, number | string | null>[];
  series: SeriesDef[];
  height?: number;
  referenceLines?: { y: number; label?: string }[];
  yDomain?: [number | "auto", number | "auto"];
}

export function MiniLineChart({ data, series, height = 160, referenceLines = [], yDomain }: Props) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
        <XAxis dataKey="date" tick={{ fontSize: 10, fill: "var(--text-muted)" }} minTickGap={40} />
        <YAxis
          tick={{ fontSize: 10, fill: "var(--text-muted)" }}
          width={44}
          domain={yDomain ?? ["auto", "auto"]}
        />
        <Tooltip
          contentStyle={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
        />
        {referenceLines.map((r, i) => (
          <ReferenceLine key={i} y={r.y} stroke="var(--text-muted)" strokeDasharray="4 4" label={{ value: r.label, fontSize: 10, fill: "var(--text-muted)" }} />
        ))}
        {series.map((s) => (
          <Line key={s.key} type="monotone" dataKey={s.key} name={s.label} stroke={s.color} strokeWidth={1.75} dot={false} isAnimationActive={false} connectNulls />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
