export function ConfidencePill({
  label,
  tone,
}: {
  label: string;
  tone: "high" | "medium" | "low";
}) {
  return <span className={`confidence-pill ${tone}`}>{label}</span>;
}
