import { CtaBand } from "@/components/landing/CtaBand";
import { Faq } from "@/components/landing/Faq";
import { GraphTeaser } from "@/components/landing/GraphTeaser";
import { Hero } from "@/components/landing/Hero";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { RiskShowcase } from "@/components/landing/RiskShowcase";
import { SourcesStrip } from "@/components/landing/SourcesStrip";
import { ToolCards } from "@/components/landing/ToolCards";
import { TrustPrinciples } from "@/components/landing/TrustPrinciples";

export default function Home() {
  return (
    <main>
      <Hero />
      <SourcesStrip />
      <ToolCards />
      <HowItWorks />
      <RiskShowcase />
      <GraphTeaser />
      <TrustPrinciples />
      <Faq />
      <CtaBand />
    </main>
  );
}
