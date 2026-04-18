export function TagChip({
  label,
  tone = "default",
}: {
  label: string;
  tone?: "default" | "insight";
}) {
  return <span className={`tag-chip ${tone}`}>{label}</span>;
}
