import { SetupWizard } from "@/components/setup-wizard";
import type { ReactNode } from "react";

export default function SetupPage(): ReactNode {
  return (
    <main className="relative min-h-dvh bg-background">
      <div className="pt-32 pb-20">
        <div className="text-center mb-4">
          <span className="inline-flex items-center gap-2 rounded-xl border border-border bg-muted px-4 py-1.5 text-sm font-medium text-foreground">
            Identity Setup
          </span>
        </div>
        <SetupWizard />
      </div>
    </main>
  );
}
