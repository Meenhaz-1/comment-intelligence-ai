type SaveRateBadgeProps = {
  tier: "high" | "medium" | "low" | "na";
};

export function SaveRateBadge({ tier }: SaveRateBadgeProps) {
  const label =
    tier === "high"
      ? "High"
      : tier === "medium"
        ? "Medium"
        : tier === "low"
          ? "Low"
          : "N/A";

  return (
    <span className={`save-rate-badge ${tier}`}>
      {label}
    </span>
  );
}
