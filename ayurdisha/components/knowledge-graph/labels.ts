export type LabelInfo = {
  color: string;
  lightColor: string;
  title: string;
  icon: string;
};

export const LABELS: Record<
  string,
  { color: string; lightColor: string; title: string; icon: string }
> = {
  Herb: {
    color: "#10b981",
    lightColor: "#10b98120",
    title: "Herb",
    icon: "🌿",
  },
  Formulation: {
    color: "#f59e0b",
    lightColor: "#f59e0b20",
    title: "Formulation",
    icon: "💊",
  },
  Ingredient: {
    color: "#84cc16",
    lightColor: "#84cc1620",
    title: "Classical ingredient",
    icon: "🧪",
  },
  Compound: {
    color: "#8b5cf6",
    lightColor: "#8b5cf620",
    title: "Compound",
    icon: "🧪",
  },
  Product: {
    color: "#3b82f6",
    lightColor: "#3b82f620",
    title: "Product",
    icon: "📦",
  },
  Source: {
    color: "#64748b",
    lightColor: "#64748b20",
    title: "Retrieved source",
    icon: "🔗",
  },
  Document: {
    color: "#06b6d4",
    lightColor: "#06b6d420",
    title: "Corpus document",
    icon: "📄",
  },
  Patent: {
    color: "#f43f5e",
    lightColor: "#f43f5e20",
    title: "Patent",
    icon: "📜",
  },
  Category: {
    color: "#f97316",
    lightColor: "#f9731620",
    title: "Therapeutic category",
    icon: "🏷️",
  },
  Name: {
    color: "#94a3b8",
    lightColor: "#94a3b820",
    title: "Vernacular name",
    icon: "🔤",
  },
};

const resolveLabel = (label: string) =>
  LABELS[label] ??
  (label
    ? Object.entries(LABELS).find(([k]) => k.toLowerCase() === label.toLowerCase())?.[1]
    : undefined);

export const labelColor = (label: string) => resolveLabel(label)?.color ?? "#737373";

export const labelLightColor = (label: string) =>
  resolveLabel(label)?.lightColor ?? "#73737320";

export const labelIcon = (label: string) => resolveLabel(label)?.icon ?? "●";
