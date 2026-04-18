import { notFound } from "next/navigation";

import { EditorHeader } from "@/components/dashboard/editor-header";
import { InterpretationLegend } from "@/components/dashboard/interpretation-legend";
import { MetricsRow } from "@/components/dashboard/metrics-row";
import { RecipesTable } from "@/components/dashboard/recipes-table";
import { TopRecipesCard } from "@/components/dashboard/top-recipes-card";
import { TopRecipesToFix } from "@/components/dashboard/top-recipes-to-fix";
import { PageShell } from "@/components/layout/page-shell";
import { getDashboardData } from "@/lib/data/dashboard";

type PageProps = {
  params: Promise<{ editorId: string }>;
};

export default async function EditorDashboardPage({ params }: PageProps) {
  const { editorId } = await params;
  const dashboard = getDashboardData(editorId);

  if (!dashboard) {
    notFound();
  }

  return (
    <PageShell>
      <EditorHeader editor={dashboard.editor} />

      <TopRecipesToFix recipes={dashboard.topRecipesToFix} />

      <section className="secondary-section">
        <div className="secondary-section-head">
          <div className="label">Performance Context</div>
          <p className="section-copy secondary-copy">
            Supporting analytics for portfolio context after the editorial backlog.
          </p>
        </div>

        <MetricsRow
          className="secondary-metrics"
          items={[
            {
              label: "Total Recipes",
              value: dashboard.totalRecipes.toString(),
              footnote: "Current owned recipe set",
            },
            {
              label: "Total Pageviews",
              value: dashboard.totalPageviewsFormatted,
              footnote: "Reach across all recipes",
            },
            {
              label: "Total Saves",
              value: dashboard.totalSavesFormatted,
              footnote: "Intent across all recipes",
            },
          ]}
        />

        <div className="tops-grid secondary-grid">
          <TopRecipesCard
            title="Highest reach"
            subtitle="Recipes attracting the most traffic"
            items={dashboard.highestReach}
            primaryMetricKey="pageviews"
            secondaryMetricKey="saves"
          />
          <TopRecipesCard
            title="Highest intent"
            subtitle="Recipes earning the most saves"
            items={dashboard.highestIntent}
            primaryMetricKey="saves"
            secondaryMetricKey="pageviews"
          />
          <TopRecipesCard
            title="High Reach, Low Conversion"
            subtitle="High traffic but low saves"
            items={dashboard.highReachLowConversion}
            primaryMetricKey="pageviews"
            secondaryMetricKey="saves"
            showSaveRate
          />
        </div>

        <InterpretationLegend />
      </section>

      <RecipesTable recipes={dashboard.recipes} />
    </PageShell>
  );
}
