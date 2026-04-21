export function RagEmptyState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="rag-empty-state">
      <div className="label">{title}</div>
      <p className="detail-muted rag-empty-copy">{description}</p>
    </div>
  );
}
