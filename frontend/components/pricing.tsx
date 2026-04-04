"use client";

import { motion } from "motion/react";
import { Check } from "lucide-react";
import HlsVideo from "./HlsVideo";
import type { ReactNode } from "react";

const HLS_SRC = "https://stream.mux.com/NcU3HlHeF7CUL86azTTzpy3Tlb00d6iF3BmCdFslMJYM.m3u8";

const plans = [
  {
    name: "Sandbox",
    price: 0,
    monthlyPrice: 0,
    description: "Free forever on local Canton sandbox",
    features: ["Unlimited Contracts", "Local Sandbox Deploy", "Security Audit Reports", "Community Support"],
    popular: false,
  },
  {
    name: "DevNet",
    price: 49,
    monthlyPrice: 69,
    description: "For teams building production-ready DAML apps",
    features: ["10 Party Identities", "Canton DevNet Deploy", "RAG Pattern Library", "Priority Support"],
    popular: true,
  },
  {
    name: "MainNet",
    price: 199,
    monthlyPrice: 249,
    description: "Full Canton Network deployment at scale",
    features: ["Unlimited Parties", "Canton MainNet Deploy", "Custom Pattern Training", "Dedicated SLA"],
    popular: false,
  },
];

const ease = [0.23, 1, 0.32, 1] as const;

function PricingCard({
  plan,
  index,
}: {
  plan: (typeof plans)[0];
  index: number;
}): ReactNode {
  const isPopular = plan.popular;

  return (
    <motion.div
      initial={{ opacity: 0, y: 40 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-50px" }}
      transition={{ duration: 0.6, ease, delay: index * 0.1 }}
      className="relative"
    >
      <div
        className={`relative flex h-full flex-col rounded-2xl p-6 sm:p-8 ${
          isPopular
            ? "bg-accent/60 backdrop-blur-lg border-t-2 border-b-2 border-white/10"
            : "bg-white/6 backdrop-blur-md border-t-2 border-b-2 border-white/10"
        }`}
        style={{ minHeight: 240 }}
      >
        {isPopular && (
          <div className="absolute -top-4 left-1/2 -translate-x-1/2">
            <span className="inline-block rounded-full bg-accent px-4 py-1.5 text-xs font-semibold uppercase tracking-wide text-black/50">
              Most Popular
            </span>
          </div>
        )}
        <h3 className={`text-xl font-semibold ${isPopular ? 'text-black' : 'text-white'}`} style={{ fontFamily: 'EB Garamond, serif', letterSpacing: '-0.01em' }}>{plan.name}</h3>

        <div className="mt-4">
          <div className="flex items-end gap-3">
            <span className={`text-5xl font-bold tracking-tight ${isPopular ? 'text-black' : 'text-white'}`}>
              {plan.price === 0 ? "Free" : `$${plan.price}`}
            </span>
            {plan.price > 0 && <span className="mb-1 text-sm text-white/70">/month</span>}
          </div>
          <p className="mt-2 text-sm text-white/70">
            {plan.price === 0 ? "No credit card required" : `Billed annually, or $${plan.monthlyPrice}/mo billed monthly`}
          </p>
        </div>

          <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          className={`mt-6 w-full rounded-xl py-3 text-sm font-semibold transition-colors ${
            isPopular
              ? "bg-black text-white hover:brightness-95"
              : "bg-white/6 text-white hover:bg-white/8"
          }`}
        >
          Launch App
        </motion.button>

        <div className="mt-8">
          <p className="text-sm font-medium text-white/70">Includes:</p>
          <ul className="mt-4 space-y-3">
            {plan.features.map((feature) => (
              <li key={feature} className="flex items-center gap-3">
                <Check
                  className={`h-4 w-4 shrink-0 ${isPopular ? 'text-black' : 'text-white'}`}
                  strokeWidth={2.5}
                />
                <span className={`text-sm ${isPopular ? 'text-black' : 'text-white/90'}`}>{feature}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </motion.div>
  );
}

export function Pricing(): ReactNode {
  return (
    <section id="pricing" className="relative w-full bg-black text-white px-6 py-20 sm:py-28 scroll-mt-24 overflow-hidden">
      {/* HLS background behind pricing */}
      <HlsVideo
        src={HLS_SRC}
        className="absolute inset-0 w-full h-full object-cover z-0"
        style={{ filter: "saturate(0) brightness(0.35)" }}
      />

      <div className="absolute top-0 left-0 right-0 z-10" style={{ height: 180, background: "linear-gradient(to bottom, rgba(0,0,0,0.6), transparent)" }} />
      <div className="absolute bottom-0 left-0 right-0 z-10" style={{ height: 180, background: "linear-gradient(to top, rgba(0,0,0,0.6), transparent)" }} />

      <div className="mx-auto max-w-5xl relative z-20">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, ease }}
          className="mb-12 text-center sm:mb-16"
        >
        
          <h2 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl lg:text-5xl" style={{ fontFamily: 'EB Garamond, serif', letterSpacing: '-0.02em' }}>
            Simple, transparent pricing
          </h2>
          <p className="mx-auto mt-4 max-w-2xl text-base text-white/70 sm:text-lg">
            Start free on sandbox. Scale to DevNet and MainNet when you&apos;re
            ready.
          </p>
        </motion.div>

        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 lg:gap-8">
          {plans.map((plan, index) => (
            <PricingCard key={plan.name} plan={plan} index={index} />
          ))}
        </div>
      </div>
    </section>
  );
}
