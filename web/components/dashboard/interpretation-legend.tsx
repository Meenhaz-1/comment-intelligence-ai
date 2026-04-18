import { TagChip } from "./tag-chip";

const LEGEND_ITEMS = [
  {
    label: "High Performer",
    description: "High save rate and strong reach within this recipe creator's portfolio.",
  },
  {
    label: "Low Conversion",
    description: "Strong traffic, but saves are underperforming relative to the creator's other recipes.",
  },
  {
    label: "Highly Discussed",
    description: "This recipe is attracting an unusually high amount of conversation.",
  },
  {
    label: "Low Visibility",
    description: "Lower traffic relative to the creator's overall recipe set.",
  },
];

export function InterpretationLegend() {
  return (
    <section className="card card-pad legend-card">
      <div className="legend-head">
        <div>
          <h3 className="section-title">How to read the labels</h3>
          <p className="section-copy">
            Each recipe gets one interpretation tag based on performance relative to this
            recipe creator&apos;s own portfolio.
          </p>
        </div>
      </div>

      <div className="legend-grid">
        {LEGEND_ITEMS.map((item) => (
          <div className="legend-item" key={item.label}>
            <TagChip label={item.label} tone="insight" />
            <p className="legend-copy">{item.description}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
