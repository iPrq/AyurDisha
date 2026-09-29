import { Reveal } from "@/components/motion/Reveal";
import { Accent, SectionHeading } from "./SectionHeading";

const FAQ = [
  {
    q: "Is this legal advice?",
    a: "No. AyurDisha is decision support. It helps you understand where your product stands and which questions to take to a registered patent agent or regulatory consultant.",
  },
  {
    q: "What sources does it use?",
    a: "A curated corpus of 17 documents, including the Patents Act 1970 (Section 3), the Biological Diversity Act 2002 and the 2014 ABS regulations, the Drugs & Cosmetics Act 1940, the Ayurvedic Pharmacopoeia and Formulary of India, CGPDTM examination guidelines and landmark cases, plus web results for international scope.",
  },
  {
    q: "Can I upload a PDF instead of typing?",
    a: "Yes. Each tool accepts a PDF dossier or disclosure. Text is extracted (scanned pages are OCR'd) and the product and ingredients are pre-filled for you to review before running the analysis.",
  },
  {
    q: "What does the Section 3 risk score mean?",
    a: "It is a rule-based indicator weighted towards 3(d), 3(e) and 3(p), not a probability that a patent will be granted. The separate grant-likelihood estimate is model-generated, comes with a confidence level and is not calibrated against Patent Office outcomes.",
  },
  {
    q: "What is NBA / ABS?",
    a: "Access and Benefit Sharing under the Biological Diversity Act. The NBA / ABS tool checks whether your use of biological resources needs National Biodiversity Authority approval and estimates the benefit-sharing rate and fee.",
  },
];

export function Faq() {
  return (
    <section className="mx-auto max-w-3xl px-4 py-24 sm:px-6">
      <Reveal className="space-y-10">
        <SectionHeading
          eyebrow="FAQ"
          title={
            <>
              Questions, <Accent>answered</Accent>
            </>
          }
        />
        <div className="space-y-3">
          {FAQ.map((f) => (
            <details
              key={f.q}
              data-reveal
              className="group rounded-2xl border border-line bg-surface px-6 py-4 shadow-soft open:pb-5"
            >
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-display font-bold [&::-webkit-details-marker]:hidden">
                {f.q}
                <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-mint text-leaf transition-transform group-open:rotate-45">
                  +
                </span>
              </summary>
              <p className="mt-3 text-muted">{f.a}</p>
            </details>
          ))}
        </div>
      </Reveal>
    </section>
  );
}
