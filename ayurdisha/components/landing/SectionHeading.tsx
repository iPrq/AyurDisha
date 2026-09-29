export function SectionHeading({
  eyebrow,
  title,
  sub,
  center = true,
}: {
  eyebrow: string;
  title: React.ReactNode;
  sub?: string;
  center?: boolean;
}) {
  return (
    <div className={`space-y-3 ${center ? "mx-auto max-w-2xl text-center" : ""}`}>
      <p
        data-reveal
        data-heading
        className="text-sm font-bold uppercase tracking-[0.18em] text-leaf"
      >
        {eyebrow}
      </p>
      <h2
        data-reveal
        data-heading
        className="font-display text-[clamp(2rem,4vw,2.75rem)] font-extrabold leading-tight tracking-tight"
      >
        {title}
      </h2>
      {sub && (
        <p data-reveal data-heading className="text-lg text-muted">
          {sub}
        </p>
      )}
    </div>
  );
}

/** Headline word in leaf green. */
export function Accent({ children }: { children: React.ReactNode }) {
  return <span className="text-leaf-bright">{children}</span>;
}
