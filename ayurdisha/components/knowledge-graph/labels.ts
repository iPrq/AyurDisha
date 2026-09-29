export const LABELS: Record<string, { color: string; title: string }> = {
  Herb: { color: "#15803d", title: "Herb" },
  Formulation: { color: "#d97706", title: "Formulation" },
  Ingredient: { color: "#84cc16", title: "Classical ingredient" },
  Compound: { color: "#7c3aed", title: "Compound" },
  Product: { color: "#2563eb", title: "Product" },
  Source: { color: "#64748b", title: "Retrieved source" },
  Document: { color: "#0891b2", title: "Corpus document" },
  Patent: { color: "#e11d48", title: "Patent" },
  Category: { color: "#ea580c", title: "Therapeutic category" },
  Name: { color: "#a3a3a3", title: "Vernacular name" },
};

export const labelColor = (label: string) => LABELS[label]?.color ?? "#737373";
