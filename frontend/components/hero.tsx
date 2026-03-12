"use client";

import { motion } from "motion/react";
import {
  ArrowRight,
  ArrowDown,
  Zap,
  Shield,
  Loader2,
} from "lucide-react";
import { useRef, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import GradientText from "./gradient-text";

const FloatingLines = dynamic(
  () => import("./floating-lines"),
  { ssr: false }
);

export function Hero(): ReactNode {
  const sectionRef = useRef<HTMLElement>(null);
  const [prompt, setPrompt] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const router = useRouter();

  const handleSubmit = async () => {
    if (!prompt.trim() || isSubmitting) return;
    setIsSubmitting(true);
    setError("");
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"}/generate`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "ngrok-skip-browser-warning": "true",
          },
          body: JSON.stringify({ prompt, canton_environment: "sandbox" }),
        }
      );
      if (response.ok) {
        const data = await response.json();
        router.push(`/sandbox/${data.job_id}`);
      } else {
        setError("Failed to start generation. Please try again.");
        setIsSubmitting(false);
      }
    } catch {
      setError("Cannot reach backend. Make sure it is running.");
      setIsSubmitting(false);
    }
  };

  return (
    <section
      ref={sectionRef}
      className="relative flex min-h-dvh w-full items-center justify-center overflow-hidden"
    >
      {/* FloatingLines Background */}
      <div className="absolute inset-0 -z-10">
        <FloatingLines
          linesGradient={["#5227FF", "#FF9FFC", "#B19EEF"]}
          enabledWaves={["top", "middle", "bottom"]}
          lineCount={5}
          lineDistance={5}
          bendRadius={5}
          bendStrength={-0.5}
          interactive={true}
          parallax={true}
        />
      </div>

      {/* Gradient overlays */}
      <div className="pointer-events-none absolute inset-0 -z-5 bg-gradient-to-b from-[#03040A]/60 via-transparent to-[#03040A]/90" />
      <div className="pointer-events-none absolute inset-0 -z-5 bg-[radial-gradient(ellipse_at_center,transparent_0%,#03040A_75%)]" />

      {/* Content */}
      <div className="relative z-10 mx-auto flex w-full max-w-4xl flex-col items-center px-4 pt-32 pb-24 text-center sm:px-6 lg:px-8">
        {/* Badge */}
        <motion.div
          initial={{ opacity: 0, y: 15, filter: "blur(6px)" }}
          animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          transition={{ duration: 0.5, ease: [0.25, 0.46, 0.45, 0.94] }}
          className="mb-8"
        >
          <span className="inline-flex items-center gap-2 rounded-full border border-purple-500/30 bg-purple-500/10 px-4 py-1.5 text-sm font-medium text-purple-300 backdrop-blur-sm">
            <Zap className="h-3.5 w-3.5" />
            AI-Powered Canton Smart Contracts
          </span>
        </motion.div>

        {/* Heading */}
        <motion.div
          className="mb-6"
          initial={{ opacity: 0, y: 20, filter: "blur(8px)" }}
          animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          transition={{
            duration: 0.6,
            delay: 0.1,
            ease: [0.25, 0.46, 0.45, 0.94],
          }}
        >
          <h1 className="text-4xl font-bold tracking-tight text-white sm:text-5xl md:text-6xl lg:text-7xl">
            <span className="block">Describe it.</span>
            <GradientText
              colors={["#5227FF", "#FF9FFC", "#B19EEF", "#5227FF"]}
              animationSpeed={8}
              showBorder={false}
              className="block"
            >
              Ginie deploys it.
            </GradientText>
          </h1>
        </motion.div>

        {/* Subheading */}
        <motion.p
          className="mb-12 max-w-2xl text-lg text-white/50 sm:text-xl"
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{
            duration: 0.5,
            delay: 0.2,
            ease: [0.25, 0.46, 0.45, 0.94],
          }}
        >
          Describe your contract in plain English. Ginie generates, compiles,
          and deploys production-ready DAML contracts to the Canton Network.
        </motion.p>

        {/* Prompt Box */}
        <motion.div
          className="w-full max-w-2xl"
          initial={{ opacity: 0, y: 30, filter: "blur(8px)" }}
          animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          transition={{
            duration: 0.6,
            delay: 0.25,
            ease: [0.25, 0.46, 0.45, 0.94],
          }}
        >
          <div
            className="relative overflow-hidden rounded-2xl border border-white/10 bg-white/5 p-1 backdrop-blur-xl"
            style={{
              boxShadow:
                "0 0 80px rgba(168, 85, 247, 0.08), 0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.05)",
            }}
          >
            <div className="rounded-xl bg-[#0a0b14]/80 p-4">
              <textarea
                placeholder="Describe your DAML contract... e.g., Create a bond between issuer and investor with coupon payments"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit();
                  }
                }}
                disabled={isSubmitting}
                className="no-focus-ring w-full resize-none bg-transparent text-base text-white/90 placeholder:text-white/30 focus:outline-none"
                rows={3}
              />

              <div className="mt-3 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-1.5 text-xs text-white/30">
                    <Shield className="h-3 w-3" />
                    <span>Canton Sandbox</span>
                  </div>
                  <div className="h-3 w-px bg-white/10" />
                  <span className="text-xs text-white/30">
                    Shift+Enter for new line
                  </span>
                </div>

                <button
                  type="button"
                  onClick={handleSubmit}
                  disabled={!prompt.trim() || isSubmitting}
                  className="group relative flex h-10 items-center gap-2 rounded-xl bg-gradient-to-r from-purple-600 to-fuchsia-600 px-5 text-sm font-semibold text-white transition-all hover:from-purple-500 hover:to-fuchsia-500 hover:shadow-[0_0_24px_rgba(168,85,247,0.4)] disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>Generating...</span>
                    </>
                  ) : (
                    <>
                      <span>Deploy</span>
                      <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>

          {error && (
            <motion.p
              initial={{ opacity: 0, y: -5 }}
              animate={{ opacity: 1, y: 0 }}
              className="mt-3 text-center text-sm text-red-400"
            >
              {error}
            </motion.p>
          )}

          <p className="mt-5 text-center text-xs text-white/25">
            Ginie uses AI to generate Canton DAML smart contracts from your
            description.
          </p>
        </motion.div>

        {/* Quick prompts */}
        <motion.div
          className="mt-8 flex flex-wrap justify-center gap-2"
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.4 }}
        >
          {[
            "Bond contract with coupon payments",
            "Token swap between two parties",
            "Escrow with milestone releases",
          ].map((example) => (
            <button
              key={example}
              type="button"
              onClick={() => setPrompt(example)}
              className="rounded-full border border-white/8 bg-white/5 px-4 py-2 text-xs text-white/40 transition-all hover:border-purple-500/30 hover:bg-purple-500/10 hover:text-white/70"
            >
              {example}
            </button>
          ))}
        </motion.div>
      </div>

      {/* Scroll indicator */}
      <motion.div
        className="absolute inset-x-0 bottom-8 flex justify-center"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5, delay: 0.6 }}
      >
        <ArrowDown
          className="h-6 w-6 animate-bounce text-white/20"
          strokeWidth={1.5}
        />
      </motion.div>
    </section>
  );
}
