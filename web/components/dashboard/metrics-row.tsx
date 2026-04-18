import { MetricCard } from "@/components/dashboard/metric-card";

type MetricItem = {
  label: string;
  value: string;
  footnote: string;
};

export function MetricsRow({
  items,
  className = "",
}: {
  items: MetricItem[];
  className?: string;
}) {
  return (
    <section className={`metrics-grid ${className}`.trim()}>
      {items.map((item) => (
        <MetricCard key={item.label} {...item} />
      ))}
    </section>
  );
}
