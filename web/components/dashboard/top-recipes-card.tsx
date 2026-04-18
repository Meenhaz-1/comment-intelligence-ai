import Link from "next/link";

import { DashboardRecipeRow } from "@/lib/types";
import { formatCompactNumber } from "@/lib/utils/format-number";

type MetricKey = "pageviews" | "saves";

type TopRecipesCardProps = {
  title: string;
  subtitle: string;
  items: DashboardRecipeRow[];
  primaryMetricKey: MetricKey;
  secondaryMetricKey: MetricKey;
  showSaveRate?: boolean;
};

export function TopRecipesCard({
  title,
  subtitle,
  items,
  primaryMetricKey,
  secondaryMetricKey,
  showSaveRate = false,
}: TopRecipesCardProps) {
  return (
    <section className="card card-pad">
      <h2 className="section-title">{title}</h2>
      <p className="section-copy">{subtitle}</p>
      <div className="top-list">
        {items.map((item, index) => (
          <div className="top-item" key={item.contentId}>
            <div className="top-rank">{index + 1}</div>
            <div>
              <Link className="top-title top-link" href={`/recipe/${item.contentId}`}>
                {item.title}
              </Link>
              <div className="top-meta">
                {item[primaryMetricKey] === null
                  ? "N/A"
                  : formatCompactNumber(item[primaryMetricKey])}{" "}
                {primaryMetricKey}
                {" · "}
                {item[secondaryMetricKey] === null
                  ? "N/A"
                  : formatCompactNumber(item[secondaryMetricKey])}{" "}
                {secondaryMetricKey}
                {showSaveRate
                  ? ` · ${item.saveRate === null ? "N/A" : `${Math.round(item.saveRate * 1000) / 10}%`} save rate`
                  : ""}
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
