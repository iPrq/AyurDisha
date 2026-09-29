"use client";

import { AgentProvider, useAgent } from "./AgentProvider";
import { AssistantDock } from "./AssistantDock";

function Frame({ children }: { children: React.ReactNode }) {
  const { dockOpen } = useAgent();
  return (
    <div className={`flex min-h-full flex-1 flex-col transition-[padding] duration-200 ${dockOpen ? "sm:pr-[380px] sm:[--dock:380px]" : ""}`}>
      {children}
      <AssistantDock />
    </div>
  );
}

export function AgentShell({ children }: { children: React.ReactNode }) {
  return (
    <AgentProvider>
      <Frame>{children}</Frame>
    </AgentProvider>
  );
}
