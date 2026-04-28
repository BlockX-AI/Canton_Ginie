"use client";

import { LogoLoop, type LogoItem } from "@/components/logo-loop";
import { ArrowDownRight, Send, Users, FileCode, Shield, Loader2, CheckCircle2 } from "lucide-react";
import { motion, useMotionValue, useSpring } from "motion/react";
import { useRef, useState, type ReactNode, type MouseEvent, type FormEvent } from "react";
import { useAuth } from "@/lib/auth-context";

const ease = [0.23, 1, 0.32, 1] as const;

const fadeInUp = {
  hidden: { opacity: 0, y: 20, filter: "blur(8px)" },
  visible: { opacity: 1, y: 0, filter: "blur(0px)" },
};

const fadeInScale = {
  hidden: { opacity: 0, scale: 0.95, filter: "blur(8px)" },
  visible: { opacity: 1, scale: 1, filter: "blur(0px)" },
};

const techLogos: LogoItem[] = [
  { node: <span className="text-base font-bold tracking-wide text-white drop-shadow-md">Canton Network</span> },
  { node: <span className="text-base font-bold tracking-wide text-white drop-shadow-md">DAML</span> },
  { node: <span className="text-base font-bold tracking-wide text-white drop-shadow-md">Digital Asset</span> },
  { node: <span className="text-base font-bold tracking-wide text-white drop-shadow-md">Ed25519</span> },
  { node: <span className="text-base font-bold tracking-wide text-white drop-shadow-md">ChromaDB</span> },
  { node: <span className="text-base font-bold tracking-wide text-white drop-shadow-md">LangGraph</span> },
  { node: <span className="text-base font-bold tracking-wide text-white drop-shadow-md">PostgreSQL</span> },
  { node: <span className="text-base font-bold tracking-wide text-white drop-shadow-md">GPT-4o</span> },
];

const PARALLAX_INTENSITY = 20;

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export function Hero(): ReactNode {
  const sectionRef = useRef<HTMLElement>(null);
  const [prompt, setPrompt] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { token, isAuthenticated, partyId, needsParty } = useAuth();
  // A user with a party already shouldn't be re-prompted to allocate one;
  // we surface a passive ``Party Generated`` confirmation instead so the
  // CTA real-estate stays useful without encouraging duplicate parties
  // in the same session.
  const hasParty = isAuthenticated && !!partyId && !needsParty;
  
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);
  
  const springConfig = { damping: 25, stiffness: 150 };
  const x = useSpring(mouseX, springConfig);
  const y = useSpring(mouseY, springConfig);

  const handleMouseMove = (e: MouseEvent<HTMLElement>) => {
    if (!sectionRef.current) return;
    if (window.innerWidth < 850) return;
    const rect = sectionRef.current.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    const offsetX = (e.clientX - centerX) / (rect.width / 2);
    const offsetY = (e.clientY - centerY) / (rect.height / 2);
    mouseX.set(offsetX * PARALLAX_INTENSITY);
    mouseY.set(offsetY * PARALLAX_INTENSITY);
  };

  const handleMouseLeave = () => {
    mouseX.set(0);
    mouseY.set(0);
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || isSubmitting) return;
    setIsSubmitting(true);
    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (isAuthenticated && token) {
        headers["Authorization"] = `Bearer ${token}`;
      }
      const resp = await fetch(`${API_URL}/generate`, {
        method: "POST",
        headers,
        body: JSON.stringify({ prompt: prompt.trim(), deploy: true }),
      });
      const data = await resp.json();
      if (data.job_id) {
        window.location.href = `/sandbox/${data.job_id}`;
      }
    } catch {
      // silently fail — user can retry
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section 
      ref={sectionRef}
      className="flex flex-col relative" 
      style={{ colorScheme: 'light' }}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
    >
      <motion.div 
        className="absolute inset-0 min-[850px]:inset-2.5 bg-cover bg-center bg-no-repeat -z-10 brightness-125 rounded-br-4xl rounded-bl-4xl min-[850px]:scale-105"
        style={{ 
          backgroundImage: 'url(/BG.jpg)',
          x,
          y,
        }}
        aria-hidden="true"
      />
      
      <div className="flex items-start justify-center px-6 pt-64 max-[850px]:pt-32">
        <motion.div
          className="flex flex-col items-center max-[850px]:items-start text-center max-[850px]:text-left max-w-4xl max-[850px]:w-full"
          initial="hidden"
          animate="visible"
          transition={{ staggerChildren: 0.15, delayChildren: 0.2 }}
        >
          <motion.div
            className="inline-flex items-center gap-1.5 pl-4 pr-3 py-1.5 rounded-xl border border-black/10 bg-white text-black text-sm font-medium mb-6"
            variants={fadeInUp}
            transition={{ duration: 0.8, ease }}
          >
            Canton Network
            <span className="text-accent">✦</span>
          </motion.div>

          <h1 className="text-8xl max-[850px]:text-5xl font-medium tracking-tight leading-[1.1] mb-6 text-black">
            <motion.span
              className="block"
              variants={fadeInUp}
              transition={{ duration: 0.8, ease }}
            >
              From Idea to
            </motion.span>
            <motion.span
              className="block"
              variants={fadeInUp}
              transition={{ duration: 0.8, ease }}
            >
              <span className="italic font-serif" style={{ color: '#22c55e' }}>Canton</span> in Minutes
            </motion.span>
          </h1>

          <motion.p
            className="text-lg text-neutral-600 mb-8 max-w-2xl"
            variants={fadeInUp}
            transition={{ duration: 0.8, ease }}
          >
            Describe your smart contract in plain English. Ginie generates production-ready DAML, compiles it, audits it, and deploys it to Canton.
          </motion.p>

          {hasParty ? (
            <motion.div
              role="status"
              aria-disabled="true"
              title="You already have a party allocated for this session"
              className="group relative inline-flex items-center max-[850px]:w-full cursor-default select-none"
              variants={fadeInScale}
              transition={{ duration: 0.8, ease }}
            >
              <span className="absolute right-0 inset-y-0 w-[calc(100%-2rem)] max-[850px]:w-full rounded-xl bg-accent/60" />
              <span className="relative z-10 px-6 py-3 rounded-xl bg-black/80 text-white/90 font-medium max-[850px]:flex-1 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-accent" />
                Party Generated
              </span>
              <span className="relative -left-px z-10 w-11 h-11 rounded-xl flex items-center justify-center text-black/70">
                <CheckCircle2 className="w-5 h-5" />
              </span>
            </motion.div>
          ) : (
            <motion.a
              href="/setup"
              className="group relative cursor-pointer inline-flex items-center max-[850px]:w-full"
              variants={fadeInScale}
              transition={{ duration: 0.8, ease }}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              <span className="absolute right-0 inset-y-0 w-[calc(100%-2rem)] max-[850px]:w-full rounded-xl bg-accent" />
              <span className="relative z-10 px-6 py-3 rounded-xl bg-black text-white font-medium max-[850px]:flex-1 flex items-center gap-2">
                <Users className="w-4 h-4" />
                Add Parties
              </span>
              <span className="relative -left-px z-10 w-11 h-11 rounded-xl flex items-center justify-center text-black">
                <ArrowDownRight className="w-5 h-5 transition-transform duration-300 group-hover:-rotate-45" />
              </span>
            </motion.a>
          )}
        </motion.div>
      </div>

      {/* Contract Description + Deploy Form (replaces dashboard image) */}
      <motion.div
        className="relative px-6 mt-24 max-[850px]:mt-10"
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 1, delay: 0.6, ease }}
      >
        <div className="relative max-w-5xl mx-auto">
          <div className="rounded-2xl overflow-hidden border border-neutral-200 bg-white shadow-2xl/10">
            {/* Form header */}
            <div className="flex items-center gap-3 px-6 py-4 border-b border-neutral-100 bg-neutral-50/50">
              <div className="flex gap-1.5">
                <div className="w-3 h-3 rounded-full bg-red-400" />
                <div className="w-3 h-3 rounded-full bg-yellow-400" />
                <div className="w-3 h-3 rounded-full bg-green-400" />
              </div>
              <span className="text-sm text-neutral-400 font-mono">ginie — contract generator</span>
            </div>

            {/* Form body */}
            <form onSubmit={handleSubmit} className="p-6 max-[850px]:p-4">
              <div className="grid grid-cols-1 min-[850px]:grid-cols-3 gap-6">
                {/* Left: Contract description */}
                <div className="min-[850px]:col-span-2 space-y-4">
                  <label className="block">
                    <span className="text-sm font-medium text-neutral-700 flex items-center gap-2 mb-2">
                      <FileCode className="w-4 h-4 text-neutral-400" />
                      Describe your contract
                    </span>
                    <textarea
                      value={prompt}
                      onChange={(e) => setPrompt(e.target.value)}
                      placeholder="e.g. Create a bond contract between an issuer and investor with a fixed coupon rate, maturity date, and early redemption option..."
                      rows={6}
                      className="w-full px-4 py-3 rounded-xl border border-neutral-200 bg-white text-neutral-900 placeholder:text-neutral-400 focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent resize-none text-sm"
                    />
                  </label>

                  <button
                    type="submit"
                    disabled={!prompt.trim() || isSubmitting}
                    className="flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-black text-white font-medium text-sm transition-all hover:bg-neutral-800 disabled:opacity-50 disabled:cursor-not-allowed w-full min-[850px]:w-auto"
                  >
                    {isSubmitting ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Generating...
                      </>
                    ) : (
                      <>
                        <Send className="w-4 h-4" />
                        Generate & Deploy
                      </>
                    )}
                  </button>

                  <p className="text-[11px] text-neutral-400 text-center min-[850px]:text-left">
                    Canton.Ginie is an AI and can make mistakes. Check important info before deploying to a production network.
                  </p>
                </div>

                {/* Right: Pipeline info */}
                <div className="space-y-3">
                  <span className="text-sm font-medium text-neutral-700 flex items-center gap-2 mb-1">
                    <Shield className="w-4 h-4 text-neutral-400" />
                    Pipeline
                  </span>
                  {[
                    { step: "Intent Analysis", desc: "Understand your requirements" },
                    { step: "Pattern Search", desc: "Find matching DAML patterns" },
                    { step: "Code Generation", desc: "AI writes production DAML" },
                    { step: "Compilation", desc: "Verify with DAML SDK" },
                    { step: "Security Audit", desc: "Automated vulnerability checks" },
                    { step: "Deploy to Canton", desc: "Live on the ledger" },
                  ].map((item, i) => (
                    <div key={i} className="flex items-start gap-3 py-2 px-3 rounded-lg bg-neutral-50 border border-neutral-100">
                      <span className="flex-none w-5 h-5 rounded-full bg-accent/20 text-[10px] font-bold flex items-center justify-center text-neutral-600 mt-0.5">
                        {i + 1}
                      </span>
                      <div>
                        <div className="text-xs font-medium text-neutral-800">{item.step}</div>
                        <div className="text-[11px] text-neutral-400">{item.desc}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </form>
          </div>
        </div>
      </motion.div>

      <motion.div
        className="pt-24 pb-12"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.8, delay: 1, ease }}
      >
        <LogoLoop logos={techLogos} speed={60} logoHeight={42} gap={124} />
      </motion.div>
    </section>
  );
}
