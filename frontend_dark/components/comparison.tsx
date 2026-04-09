"use client";

import { motion } from "motion/react";
import { Shield, Globe, ClipboardCheck, Check, X, AlertTriangle, Minus } from "lucide-react";
import type { ReactNode } from "react";

// ---------------------------------------------------------------------------
// Data
// ---------------------------------------------------------------------------

type CellValue =
  | { type: "yes"; label?: string }
  | { type: "no"; label?: string }
  | { type: "partial"; label?: string }
  | { type: "warn"; label?: string }
  | { type: "text"; label: string }
  | { type: "na" };

interface Row {
  feature: string;
  ginie: CellValue;
  damlAutopilot: CellValue;
  chainSafeMcp: CellValue;
  manualDev: CellValue;
}

const rows: Row[] = [
  { feature: "Interface", ginie: { type: "text", label: "Web App" }, damlAutopilot: { type: "text", label: "IDE Plugin" }, chainSafeMcp: { type: "text", label: "IDE Plugin" }, manualDev: { type: "text", label: "CLI / IDE" } },
  { feature: "Target User", ginie: { type: "text", label: "Anyone" }, damlAutopilot: { type: "text", label: "Developer" }, chainSafeMcp: { type: "text", label: "Developer" }, manualDev: { type: "text", label: "Daml Expert" } },
  { feature: "Daml Knowledge Required", ginie: { type: "no", label: "None" }, damlAutopilot: { type: "yes", label: "Moderate" }, chainSafeMcp: { type: "yes", label: "Moderate" }, manualDev: { type: "yes", label: "Extensive" } },
  { feature: "Natural Language → Contract", ginie: { type: "yes" }, damlAutopilot: { type: "yes" }, chainSafeMcp: { type: "yes" }, manualDev: { type: "no" } },
  { feature: "Real Compilation (not just text)", ginie: { type: "yes" }, damlAutopilot: { type: "yes" }, chainSafeMcp: { type: "yes" }, manualDev: { type: "no" } },
  { feature: "Auto Fix Loop on Errors", ginie: { type: "yes", label: "11 error types" }, damlAutopilot: { type: "no" }, chainSafeMcp: { type: "no" }, manualDev: { type: "text", label: "Manual" } },
  { feature: "One-Click Deploy to Canton", ginie: { type: "yes" }, damlAutopilot: { type: "no", label: "Manual" }, chainSafeMcp: { type: "no", label: "Manual" }, manualDev: { type: "text", label: "Manual" } },
  { feature: "Pre-deployment Security Audit", ginie: { type: "yes" }, damlAutopilot: { type: "no" }, chainSafeMcp: { type: "partial", label: "Partial" }, manualDev: { type: "text", label: "Manual" } },
  { feature: "Compliance Report (PDF/HTML)", ginie: { type: "yes" }, damlAutopilot: { type: "no" }, chainSafeMcp: { type: "no" }, manualDev: { type: "text", label: "Manual" } },
  { feature: "Verified Pattern Library", ginie: { type: "text", label: "~500" }, damlAutopilot: { type: "text", label: "3,667" }, chainSafeMcp: { type: "text", label: "3,667" }, manualDev: { type: "na" } },
  { feature: "Multi-user Web Access", ginie: { type: "yes" }, damlAutopilot: { type: "no" }, chainSafeMcp: { type: "no" }, manualDev: { type: "no" } },
  { feature: "Persistent Job History", ginie: { type: "yes", label: "PostgreSQL" }, damlAutopilot: { type: "no" }, chainSafeMcp: { type: "no" }, manualDev: { type: "text", label: "Manual" } },
  { feature: "Canton Party Management", ginie: { type: "yes", label: "Per-user" }, damlAutopilot: { type: "no" }, chainSafeMcp: { type: "no" }, manualDev: { type: "text", label: "Manual CLI" } },
  { feature: "Ledger Explorer UI", ginie: { type: "yes" }, damlAutopilot: { type: "no" }, chainSafeMcp: { type: "no" }, manualDev: { type: "no" } },
  { feature: "Air-gapped / Private Mode", ginie: { type: "yes", label: "Ginie-1 (M4)" }, damlAutopilot: { type: "no", label: "Cloud only" }, chainSafeMcp: { type: "no" }, manualDev: { type: "yes" } },
  { feature: "Cost Model", ginie: { type: "text", label: "Free / Grant" }, damlAutopilot: { type: "text", label: "Pay-per-use" }, chainSafeMcp: { type: "text", label: "Free OSS" }, manualDev: { type: "text", label: "Time cost" } },
  { feature: "Open Source", ginie: { type: "yes", label: "Apache 2.0" }, damlAutopilot: { type: "partial", label: "Partially" }, chainSafeMcp: { type: "yes" }, manualDev: { type: "na" } },
  { feature: "Works Without Internet", ginie: { type: "yes", label: "Ginie-1 (M4)" }, damlAutopilot: { type: "no" }, chainSafeMcp: { type: "no" }, manualDev: { type: "yes" } },
  { feature: "Institutional Audit Trail", ginie: { type: "yes" }, damlAutopilot: { type: "no" }, chainSafeMcp: { type: "no" }, manualDev: { type: "no" } },
  { feature: "From Prompt to Contract ID", ginie: { type: "text", label: "~35 sec" }, damlAutopilot: { type: "text", label: "Manual steps" }, chainSafeMcp: { type: "text", label: "Manual steps" }, manualDev: { type: "text", label: "Hours/Days" } },
];

const audiences = [
  { tool: "MCP Tools", who: "For developers", access: "IDE only", audit: "No audit" },
  { tool: "Daml Autopilot", who: "For developers", access: "IDE only", audit: "No audit" },
  { tool: "Ginie", who: "For everyone", access: "Web browser", audit: "Full audit trail" },
];

const moatItems = [
  { icon: Shield, text: "Only platform with pre-deployment compliance reports", color: "text-amber-400" },
  { icon: Globe, text: "Web app — no IDE, no Daml knowledge, no DevNet credentials needed", color: "text-cyan-400" },
  { icon: ClipboardCheck, text: "Audit trail + job history — enterprise and regulated institution ready", color: "text-amber-400" },
];

// ---------------------------------------------------------------------------
// Cell renderer
// ---------------------------------------------------------------------------

function Cell({ value, isGinie }: { value: CellValue; isGinie?: boolean }) {
  switch (value.type) {
    case "yes":
      return (
        <span className="inline-flex items-center gap-1.5">
          <Check className={`h-4 w-4 shrink-0 ${isGinie ? "text-accent" : "text-green-400"}`} />
          {value.label && <span className="text-white/60 text-xs">{value.label}</span>}
        </span>
      );
    case "no":
      return (
        <span className="inline-flex items-center gap-1.5">
          <X className="h-4 w-4 shrink-0 text-red-400" />
          {value.label && <span className="text-white/40 text-xs">{value.label}</span>}
        </span>
      );
    case "partial":
      return (
        <span className="inline-flex items-center gap-1.5">
          <Minus className="h-4 w-4 shrink-0 text-amber-400" />
          {value.label && <span className="text-white/50 text-xs">{value.label}</span>}
        </span>
      );
    case "warn":
      return (
        <span className="inline-flex items-center gap-1.5">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-amber-400" />
          {value.label && <span className="text-white/50 text-xs">{value.label}</span>}
        </span>
      );
    case "text":
      return <span className={`text-xs ${isGinie ? "text-white font-medium" : "text-white/60"}`}>{value.label}</span>;
    case "na":
      return <span className="text-xs text-white/20">N/A</span>;
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const ease = [0.23, 1, 0.32, 1] as const;

export function Comparison(): ReactNode {
  return (
    <section id="comparison" className="relative bg-black py-24 px-6">
      <div className="mx-auto max-w-6xl">
        {/* Section heading */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, ease }}
          className="text-center mb-16"
        >
          <h2
            className="text-4xl md:text-5xl text-white font-medium"
            style={{ fontFamily: "EB Garamond, serif" }}
          >
            Ginie vs. The Ecosystem
          </h2>
          <p className="mt-4 text-white/50 text-sm md:text-base max-w-2xl mx-auto">
            Feature comparison for institutional Canton builders
          </p>
        </motion.div>

        {/* Positioning statement */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.1, ease }}
          className="mb-12 rounded-2xl border border-white/10 bg-white/[0.03] p-6 md:p-8"
        >
          <div className="border-l-2 border-accent pl-5">
            <p className="text-white/80 text-sm md:text-base leading-relaxed italic">
              &ldquo;Daml Autopilot and ChainSafe MCP are powerful tools for developers who already know Daml.
              Ginie is the only platform where a Goldman Sachs product manager, a compliance officer at Euroclear,
              or a university student with zero blockchain experience can describe a contract in English and receive
              a verified, audited, live Contract ID on Canton — in 90 seconds.&rdquo;
            </p>
          </div>
        </motion.div>

        {/* ── Section 1: "Who is it for?" cards ── */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.15, ease }}
          className="mb-12"
        >
          <h3 className="text-lg font-semibold text-white mb-5">Who is it for?</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {audiences.map((a) => (
              <div
                key={a.tool}
                className={`rounded-xl border p-5 transition-all ${
                  a.tool === "Ginie"
                    ? "border-accent/40 bg-accent/5 ring-1 ring-accent/20"
                    : "border-white/10 bg-white/[0.02]"
                }`}
              >
                <h4 className={`text-sm font-bold mb-3 ${a.tool === "Ginie" ? "text-accent" : "text-white/70"}`}>
                  {a.tool}
                </h4>
                <ul className="space-y-1.5 text-xs">
                  <li className={a.tool === "Ginie" ? "text-white" : "text-white/50"}>{a.who}</li>
                  <li className={a.tool === "Ginie" ? "text-white" : "text-white/50"}>{a.access}</li>
                  <li className={a.tool === "Ginie" ? "text-white" : "text-white/50"}>{a.audit}</li>
                </ul>
              </div>
            ))}
          </div>
        </motion.div>

        {/* ── Section 2: Full comparison table ── */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.2, ease }}
          className="mb-12 overflow-x-auto"
        >
          <table className="w-full min-w-[700px] text-left border-collapse">
            <thead>
              <tr className="border-b border-white/10">
                <th className="py-3 pr-4 text-[11px] font-semibold uppercase tracking-wider text-white/40 w-[22%]">Feature</th>
                <th className="py-3 px-3 text-[11px] font-semibold uppercase tracking-wider text-accent w-[18%]">Ginie</th>
                <th className="py-3 px-3 text-[11px] font-semibold uppercase tracking-wider text-white/40 w-[20%]">Daml Autopilot</th>
                <th className="py-3 px-3 text-[11px] font-semibold uppercase tracking-wider text-white/40 w-[20%]">ChainSafe MCP</th>
                <th className="py-3 px-3 text-[11px] font-semibold uppercase tracking-wider text-white/40 w-[20%]">Manual Dev</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr
                  key={row.feature}
                  className={`border-b border-white/5 ${i % 2 === 0 ? "bg-white/[0.01]" : ""}`}
                >
                  <td className="py-2.5 pr-4 text-xs text-white/70 font-medium">{row.feature}</td>
                  <td className="py-2.5 px-3"><Cell value={row.ginie} isGinie /></td>
                  <td className="py-2.5 px-3"><Cell value={row.damlAutopilot} /></td>
                  <td className="py-2.5 px-3"><Cell value={row.chainSafeMcp} /></td>
                  <td className="py-2.5 px-3"><Cell value={row.manualDev} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </motion.div>

        {/* ── Section 3: The Ginie Moat ── */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.25, ease }}
          className="mb-12"
        >
          <h3 className="text-lg font-semibold text-white mb-5">The Ginie Moat</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {moatItems.map((item) => {
              const Icon = item.icon;
              return (
                <div
                  key={item.text}
                  className="rounded-xl border border-accent/20 bg-accent/5 p-5 flex items-start gap-3"
                >
                  <Icon className={`h-5 w-5 shrink-0 mt-0.5 ${item.color}`} />
                  <p className="text-sm text-white/80 leading-relaxed">{item.text}</p>
                </div>
              );
            })}
          </div>
        </motion.div>

        {/* ── The Honest Caveat ── */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.3, ease }}
          className="rounded-2xl border border-white/10 bg-white/[0.02] p-6 md:p-8"
        >
          <h3 className="text-sm font-semibold text-white/60 uppercase tracking-wider mb-3">
            The Honest Caveat
          </h3>
          <div className="border-l-2 border-white/20 pl-5">
            <p className="text-white/50 text-sm leading-relaxed italic">
              &ldquo;ChainSafe&apos;s Daml Autopilot has a larger verified pattern library (3,667 patterns vs. Ginie&apos;s
              current corpus). Ginie&apos;s roadmap includes expanding the pattern library to match. Where Ginie leads
              today is in end-to-end automation, compliance reporting, and accessibility for non-developer users.&rdquo;
            </p>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
