import { RECOMMENDATION_STYLES } from "../lib/format";

export function RecommendationBadge({ label }: { label: string }) {
  const style = RECOMMENDATION_STYLES[label] ?? RECOMMENDATION_STYLES["HOLD / NEUTRAL"];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${style.bg} ${style.fg}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${style.dot}`} />
      {label}
    </span>
  );
}
