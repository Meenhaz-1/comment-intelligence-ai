import { notFound } from "next/navigation";

import { MetricCard } from "@/components/dashboard/metric-card";
import { PageShell } from "@/components/layout/page-shell";
import { AppLink } from "@/components/navigation/navigation-progress";
import { CommentsPanel } from "@/components/recipe/comments-panel";
import { EditorialInsightCard } from "@/components/recipe/editorial-insight-card";
import { RagExploration } from "@/components/recipe/rag-exploration";
import { SupportingEvidence } from "@/components/recipe/supporting-evidence";
import { getRecipeDetail } from "@/lib/data/recipe-master";
import { formatNumber } from "@/lib/utils/format-number";
import { formatPercent } from "@/lib/utils/format-percent";

type PageProps = {
  params: Promise<{ contentId: string }>;
};

export default async function RecipeDetailPage({ params }: PageProps) {
  const { contentId } = await params;
  const detail = getRecipeDetail(contentId);

  if (!detail) {
    notFound();
  }

  const { recipe, comments } = detail;

  return (
    <PageShell>
      <header className="recipe-detail-hero">
        <div className="dashboard-topbar">
          <AppLink href={`/editor/${recipe.editorId}`} className="back-link">
            {"← Back to Recipe Creator"}
          </AppLink>
        </div>
        <div className="eyebrow">Recipe Notebook</div>
        <h1 className="recipe-detail-title">{recipe.title}</h1>
        <div className="recipe-hero-links">
          {recipe.url ? (
            <a
              className="external-link"
              href={recipe.url}
              rel="noreferrer"
              target="_blank"
            >
              View Recipe ↗
            </a>
          ) : null}
        </div>
        <div className="recipe-meta-row">
          <span>👩‍🍳 {recipe.authorName}</span>
          {recipe.brand ? <span>🍽️ {recipe.brand}</span> : null}
          <span>🧾 {recipe.contentId}</span>
        </div>
      </header>

      <EditorialInsightCard comments={comments} recipe={recipe} />

      <SupportingEvidence comments={comments} recipe={recipe} />

      <RagExploration recipe={recipe} />

      <CommentsPanel comments={comments} recipe={recipe} />

      <section className="detail-section secondary-section">
        <div className="secondary-section-head">
          <div className="label">Metrics</div>
          <p className="section-copy secondary-copy">
            Performance and discussion context for the editorial readout above.
          </p>
        </div>

        <section className="metrics-grid detail-metrics-grid supporting-metrics">
          <MetricCard
            footnote="Reach in the current dataset"
            icon="👁️"
            label="Total Pageviews"
            value={formatNumber(recipe.pageviews)}
          />
          <MetricCard
            footnote="Intent in the current dataset"
            icon="🔖"
            label="Total Saves"
            value={recipe.saves === null ? "N/A" : formatNumber(recipe.saves)}
          />
          <MetricCard
            footnote="Quality signal from saves ÷ pageviews"
            icon="🥄"
            label="Save Rate"
            value={formatPercent(recipe.saveRate)}
          />
          <MetricCard
            footnote="Discussion volume from comments"
            icon="💬"
            label="Total Comments"
            value={formatNumber(recipe.totalComments)}
          />
        </section>
      </section>

      <section className="card card-pad detail-section">
        <div className="detail-section-head">
          <h2 className="section-title">Recipe Details</h2>
          <div className="section-kicker">From the pantry</div>
        </div>

        <div className="detail-grid">
          <div>
            <div className="label">Tags</div>
            <div className="tag-row detail-tag-row">
              {recipe.tags.length > 0 ? (
                recipe.tags.map((tag) => (
                  <span className="tag-chip" key={tag}>
                    {tag}
                  </span>
                ))
              ) : (
                <span className="detail-muted">No tags available.</span>
              )}
            </div>
          </div>

          <div>
            <div className="label">Recipe URL</div>
            {recipe.url ? (
              <a
                className="detail-link"
                href={recipe.url}
                rel="noreferrer"
                target="_blank"
              >
                {recipe.url}
              </a>
            ) : (
              <span className="detail-muted">No recipe URL available.</span>
            )}
          </div>
        </div>
      </section>
    </PageShell>
  );
}
