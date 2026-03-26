import { Header } from "@/components/header";
import { SetupWizard } from "@/components/setup-wizard";
import type { ReactNode } from "react";

export default function SetupPage(): ReactNode {
  return (
    <main className="relative min-h-dvh bg-[#03040A]">
      <Header />
      <div className="pt-32">
        <div className="text-center mb-4">
          <span className="inline-flex items-center gap-2 rounded-full border border-purple-500/30 bg-purple-500/10 px-4 py-1.5 text-sm font-medium text-purple-300 backdrop-blur-sm">
            Identity Setup
          </span>
        </div>
        <SetupWizard />
      </div>
    </main>
  );
}
