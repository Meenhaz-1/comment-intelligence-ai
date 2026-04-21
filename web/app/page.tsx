import { EditorSelectCard } from "@/components/homepage/editor-select-card";
import { HeroHeader } from "@/components/homepage/hero-header";
import { ComingSoonGrid } from "@/components/homepage/coming-soon-grid";
import { PageShell } from "@/components/layout/page-shell";
import { AppLink } from "@/components/navigation/navigation-progress";
import { getEditors } from "@/lib/data/editors";

export default function HomePage() {
  const editors = getEditors();
  const sampleEditor = editors[0];

  return (
    <PageShell>
      <HeroHeader
        eyebrow="Editorial Kitchen"
        title="Recipe Intelligence"
        subtitle="Spot which recipes need editorial attention first, then move into the evidence behind reach, saves, and reader feedback."
      />

      <EditorSelectCard
        editors={editors}
        ctaLabel="Open recipe creator backlog"
      />

      <ComingSoonGrid
        items={[
          { title: "Recipe Health Dashboard", href: "#" },
          { title: "Theme Explorer", href: "#" },
          { title: "Ask the Comments", href: "#" },
          { title: "Portfolio View", href: "#" },
        ]}
      />

      {sampleEditor ? (
        <div style={{ marginTop: 28, textAlign: "center", color: "var(--muted)" }}>
          Quick start with{" "}
          <AppLink href={`/editor/${sampleEditor.id}`} style={{ fontWeight: 700 }}>
            {sampleEditor.name}
          </AppLink>
          {" as a Recipe Creator"}
          .
        </div>
      ) : null}
    </PageShell>
  );
}
