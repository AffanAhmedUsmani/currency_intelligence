import { Line, LineChart, ResponsiveContainer, YAxis } from "recharts";

interface Props {
  data: (number | null)[];
  positive: boolean;
  height?: number;
}

export function Sparkline({ data, positive, height = 40 }: Props) {
  const points = data
    .map((v, i) => (v === null ? null : { i, v }))
    .filter((p): p is { i: number; v: number } => p !== null);

  if (points.length < 2) {
    return <div style={{ height }} className="flex items-center text-xs text-[var(--text-muted)]">Not enough data</div>;
  }

  const color = positive ? "var(--positive)" : "var(--negative)";

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={points} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
        <YAxis domain={["dataMin", "dataMax"]} hide />
        <Line type="monotone" dataKey="v" stroke={color} strokeWidth={1.75} dot={false} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
