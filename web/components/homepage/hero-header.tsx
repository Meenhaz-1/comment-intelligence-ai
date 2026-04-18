type HeroHeaderProps = {
  eyebrow: string;
  title: string;
  subtitle: string;
};

export function HeroHeader({ eyebrow, title, subtitle }: HeroHeaderProps) {
  return (
    <section className="hero-block">
      <div className="eyebrow">{eyebrow}</div>
      <div className="hero-garnish" aria-hidden="true">
        <span>🥖</span>
        <span>🍅</span>
        <span>🌿</span>
      </div>
      <h1 className="display-title">{title}</h1>
      <p className="subtitle">{subtitle}</p>
    </section>
  );
}
