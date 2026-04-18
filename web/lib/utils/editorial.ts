export function formatEditorialIssue(value: string | null | undefined): string {
  const normalized = value?.trim();
  return normalized ? normalized : "Multiple issues";
}

export function formatEditorialFix(value: string | null | undefined): string {
  const normalized = value?.trim();
  return normalized ? normalized : "Varied modifications";
}

export function formatOpportunityScore(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(2) : "N/A";
}

export function isLowSignal(priority: string | null | undefined): boolean {
  return (priority ?? "").trim().toLowerCase() === "low signal";
}
