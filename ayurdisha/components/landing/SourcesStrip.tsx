const SOURCES = [
  "Patents Act, 1970 · Section 3",
  "Biological Diversity Act, 2002",
  "NBA ABS Regulations, 2014",
  "Drugs & Cosmetics Act, 1940",
  "Ayurvedic Pharmacopoeia of India",
  "Ayurvedic Formulary of India",
  "CGPDTM Ayush Examination Guidelines",
  "Novartis v. Union of India (2013)",
  "Turmeric patent case",
  "Bhaishajya Kalpana Kosha",
];

export function SourcesStrip() {
  return (
    <section aria-label="Sources" className="border-y border-line bg-surface py-6">
      <p className="mb-4 text-center text-xs font-bold uppercase tracking-[0.2em] text-muted">
        Grounded in 17 curated source documents
      </p>
      <div className="relative overflow-hidden [mask-image:linear-gradient(90deg,transparent,#000_10%,#000_90%,transparent)]">
        <div className="marquee flex w-max">
          {[0, 1].map((copy) => (
            <ul key={copy} aria-hidden={copy === 1} className="flex gap-3 pr-3">
              {SOURCES.map((s) => (
                <li
                  key={s}
                  className="whitespace-nowrap rounded-full border border-line bg-canvas px-4 py-2 text-sm font-medium text-muted"
                >
                  {s}
                </li>
              ))}
            </ul>
          ))}
        </div>
      </div>
    </section>
  );
}
