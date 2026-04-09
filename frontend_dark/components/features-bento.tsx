"use client";

import { motion, type Transition } from "motion/react";
import { CircleCheck, Shield } from "lucide-react";
import type { ReactNode } from "react";

const EASE = [0.23, 1, 0.32, 1] as const;

const DEPLOYMENT_STATS = [
  {  label: "1,240+ Contracts Deployed", change: "+18%" },
  {  label: "99.9% Compilation Rate", change: "+2.1%" },
];

const cardAnimation = {
  initial: { opacity: 0, y: 40 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-100px" },
};

const getCardTransition = (delay = 0): Transition => ({
  duration: 0.8,
  ease: EASE,
  delay,
});

function PhoneMockup({
  children,
  variant = "full",
}: {
  children: ReactNode;
  variant?: "full" | "compact";
}): ReactNode {
  const isCompact = variant === "compact";

  return (
    <div
      className={`
        relative bg-background shadow-2xl border-neutral-800 overflow-hidden z-10
        ${isCompact 
          ? "w-44 md:w-48 h-64 md:h-72 rounded-3xl border-4" 
          : "w-56 md:w-64 h-96 md:h-115 rounded-t-4xl border-6 border-b-0"
        }
      `}
    >
      <div
        className={`
          absolute left-1/2 -translate-x-1/2 bg-neutral-800 rounded-full z-10
          ${isCompact ? "top-2 w-16 h-4" : "top-2 w-20 h-5"}
        `}
        aria-hidden="true"
      />
      {children}
    </div>
  );
}

function DeploymentStat({
  label,
  change,
}: {
  label: string;
  change: string;
}): ReactNode {
  return (
    <div className="flex items-center justify-between bg-background rounded-xl p-3">
      <div className="flex items-center gap-2">
        <span className="text-foreground font-medium">{label}</span>
      </div>
      <span className="text-black text-sm font-medium">{change}</span>
    </div>
  );
}

function DecorativeCircles(): ReactNode {
  return (
    <div className="absolute inset-0 flex items-center justify-center" aria-hidden="true">
      <div className="absolute size-56 border border-accent/80 rounded-full" />
      <div className="absolute size-72 border border-accent/60 rounded-full" />
      <div className="absolute size-88 border border-accent/40 rounded-full" />
    </div>
  );
}

function SetupWizardCard(): ReactNode {
  return (
    <motion.div
      {...cardAnimation}
      transition={getCardTransition(0)}
      className="group bg-white/6 backdrop-blur-md border-t-2 border-b-2 border-white/10 rounded-4xl p-8 pb-0 overflow-hidden min-h-140 md:row-span-2 flex flex-col"
    >
      <div className="relative z-10 text-center mb-6 transition-transform duration-500 ease-out group-hover:scale-105">
        <h3 className="text-2xl md:text-4xl font-medium text-white leading-tight mb-3" style={{ fontFamily: "EB Garamond, serif" }}>
          Identity Setup in Seconds
        </h3>
        <p className="text-white/70 text-sm">
          Generate an Ed25519 keypair, name your party, and register on Canton all in four steps
        </p>
      </div>

      <div className="flex-1 flex justify-center items-end transition-transform duration-500 ease-out group-hover:scale-[1.02]">
        <PhoneMockup variant="full">
          <div className="absolute inset-0 bg-phone-screen pt-14 px-5">
            <h4 className="text-3xl font-medium text-neutral-900 leading-none tracking-tight mt-4">
              Your party
            </h4>
            <h4 className="text-3xl font-medium text-neutral-900 leading-none tracking-tight mb-4">
              is live!
            </h4>
            <p className="text-sm text-neutral-500 leading-snug mb-8">
              Start deploying DAML contracts to Canton instantly.
            </p>

            <div className="relative bg-linear-to-br from-accent via-accent/80 to-accent/50 rounded-2xl p-4 h-52 shadow-xl overflow-hidden">
              <svg
                className="absolute inset-0 size-full"
                viewBox="0 0 100 60"
                preserveAspectRatio="none"
                aria-hidden="true"
              >
                <path d="M0,60 Q30,40 60,50 T100,30" fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth="0.5" />
                <path d="M0,55 Q40,35 70,45 T100,25" fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="0.5" />
              </svg>
              <div className="relative z-10 flex items-start justify-between gap-3 h-full">
                <div>
                  <p className="text-base font-semibold text-neutral-900">Party::Alice</p>
                  <p className="text-xs text-neutral-700 mt-1 font-mono">canton::participant1</p>
                </div>
                <CircleCheck className="opacity-25 text-black" aria-hidden="true" />
              </div>
              <div className="absolute bottom-3 left-5 flex items-center gap-2 text-neutral-700 text-xs tracking-widest" aria-hidden="true">
                <span>ED25519</span>
                <span>•</span>
                <span>JWT</span>
                <span>•</span>
                <span>LIVE</span>
              </div>
            </div>
          </div>
        </PhoneMockup>
      </div>
    </motion.div>
  );
}

function LedgerExplorerCard(): ReactNode {
  return (
    <motion.div
      {...cardAnimation}
      transition={getCardTransition(0.1)}
      className="group bg-white/6 backdrop-blur-md border-t-2 border-b-2 border-white/10 rounded-4xl p-8 overflow-hidden min-h-80 relative flex flex-col md:block"
    >
      <div className="relative z-10 max-w-48 transition-transform duration-500 ease-out group-hover:scale-105">
        <h3 className="text-xl md:text-2xl whitespace-nowrap font-medium leading-tight mb-3" style={{ fontFamily: "EB Garamond, serif" }}>
          <span className="text-white">Ledger Explorer</span>
        </h3>
        <p className="text-white/70 text-sm">
          Browse active contracts, parties, and deployment history on Canton
        </p>
      </div>

      <div className="relative md:absolute mt-8 md:mt-0 md:right-12 md:top-1/2 md:-translate-y-1/2 flex items-center justify-center transition-transform duration-500 ease-out group-hover:scale-105 self-center md:self-auto">
        <DecorativeCircles />

        <PhoneMockup variant="compact">
          <div className="absolute inset-0 bg-phone-screen pt-9 px-3">
            <div className="bg-white rounded-full px-2 py-1.5 mb-3 flex items-center gap-1.5 border border-neutral-200">
              <span className="text-neutral-400 text-xs">Search contracts...</span>
            </div>
            <p className="text-xs text-neutral-500 mb-0.5">Active contracts</p>
            <p className="text-xl font-medium text-neutral-900 mb-3">38 deployed</p>

            <div className="flex gap-1.5 mb-4">
              <span className="bg-accent text-black text-xs px-2.5 py-1 rounded-full">
                Contracts
              </span>
              <span className="text-neutral-400 text-xs px-2 py-1">Parties</span>
              <span className="text-neutral-400 text-xs px-2 py-1">DARs</span>
            </div>
          </div>
        </PhoneMockup>

        <div className="absolute bottom-0 left-1/2 -translate-x-1/2 bg-neutral-900 rounded-2xl px-5 py-3 shadow-xl z-20 whitespace-nowrap">
          <div className="flex items-center gap-2 mb-0.5">
            <span className="text-neutral-400 text-xs">Compilation status</span>
            <span className="text-neutral-500 text-xs">ⓘ</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-lg font-medium text-white">All passing</span>
            <span className="text-xs font-medium text-accent bg-accent/20 px-2 py-0.5 rounded">
              ✓ 100%
            </span>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

function SecurityAuditCard(): ReactNode {
  return (
    <motion.div
      {...cardAnimation}
      transition={getCardTransition(0.2)}
      className="group bg-white/6 backdrop-blur-md border-t-2 border-b-2 border-white/10 rounded-4xl p-6 md:p-8 flex flex-col items-center justify-center text-center min-h-64"
    >
      <div className="transition-transform duration-500 ease-out group-hover:scale-110">
        <Shield className="size-10 text-accent mb-4 mx-auto" strokeWidth={1.5} />
        <h3 className="text-2xl md:text-3xl font-medium leading-tight mb-1" style={{ fontFamily: "EB Garamond, serif" }}>
          <span className="text-white">Security Audit</span>
        </h3>
        <h3 className="text-lg md:text-xl font-medium leading-tight mb-5">
          <span className="text-white/70">Built Into Every Deploy</span>
        </h3>
      </div>

      <div className="flex flex-col gap-2 w-full max-w-xs transition-transform duration-500 ease-out group-hover:scale-105">
        {[
          { label: "Vulnerability Scan", status: "Passed" },
          { label: "Compliance Check", status: "Passed" },
          { label: "Best Practices", status: "Passed" },
        ].map((item) => (
          <div key={item.label} className="flex items-center justify-between bg-background/50 rounded-lg px-3 py-2">
            <span className="text-xs text-card-foreground">{item.label}</span>
            <span className="text-xs font-medium text-accent">{item.status}</span>
          </div>
        ))}
      </div>
    </motion.div>
  );
}

function ScaleCard(): ReactNode {
  return (
    <motion.div
      {...cardAnimation}
      transition={getCardTransition(0.3)}
      className="group bg-white/6 backdrop-blur-md border-t-2 border-b-2 border-white/10 rounded-4xl p-6 md:p-8 flex flex-col min-h-64"
    >
      <div className="mb-auto transition-transform duration-500 ease-out group-hover:scale-105">
        <h3 className="text-xl md:text-2xl font-medium leading-tight mb-2" style={{ fontFamily: "EB Garamond, serif" }}>
          <span className="text-white">Built for Canton Scale</span>
        </h3>
        <p className="text-white/70 text-sm">
          From sandbox to DevNet to MainNet Ginie grows with your deployment
        </p>
      </div>

      <div className="flex flex-col gap-2 mt-6 transition-transform duration-500 ease-out group-hover:scale-[1.02]">
        {DEPLOYMENT_STATS.map((stat) => (
          <DeploymentStat key={stat.label} {...stat} />
        ))}
      </div>
    </motion.div>
  );
}

export function FeaturesBento(): ReactNode {
  return (
    <section className="w-full px-6 mb-0 pt-0 bg-black">
      <div className="max-w-5xl mx-auto">
        <div className="grid grid-cols-1 md:grid-cols-[1fr_1.5fr] gap-4">
          <SetupWizardCard />
          <LedgerExplorerCard />

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <SecurityAuditCard />
            <ScaleCard />
          </div>
        </div>
      </div>
    </section>
  );
}
