type ComingSoonItem = {
  title: string;
  href: string;
};

type ComingSoonGridProps = {
  items: ComingSoonItem[];
};

export function ComingSoonGrid({ items }: ComingSoonGridProps) {
  return (
    <section className="coming-soon">
      <div className="eyebrow" style={{ textAlign: "center" }}>
        Coming Soon
      </div>
      <div className="coming-soon-grid">
        {items.map((item) => (
          <a key={item.title} className="coming-soon-card" href={item.href}>
            {item.title}
          </a>
        ))}
      </div>
    </section>
  );
}
