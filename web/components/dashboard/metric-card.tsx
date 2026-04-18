type MetricCardProps = {
  label: string;
  value: string;
  footnote: string;
  icon?: string;
};

export function MetricCard({ label, value, footnote, icon }: MetricCardProps) {
  return (
    <section className="card card-pad metric-card">
      <div className="metric-label">
        {icon ? <span className="metric-icon">{icon}</span> : null}
        {label}
      </div>
      <div className="metric-value">{value}</div>
      <div className="metric-footnote">{footnote}</div>
    </section>
  );
}
