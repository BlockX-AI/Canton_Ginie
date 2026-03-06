"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { generateContract } from "@/lib/api";
import toast from "react-hot-toast";

const CONTRACT_EXAMPLES = [
  {
    label: "Bond Tokenization",
    prompt: "I want a bond tokenization contract where Goldman Sachs can issue fixed-rate bonds to pension fund investors with 5% annual coupon payments, redemption at maturity, and full party-based privacy on Canton Network.",
  },
  {
    label: "Equity Token",
    prompt: "Create an equity token contract for TechCorp Inc. where the company can issue fractional shares to investors, pay dividends, and allow shareholders to vote on company proposals.",
  },
  {
    label: "Escrow",
    prompt: "Build an escrow contract with a buyer, seller, and neutral escrow agent. The buyer deposits funds, seller delivers goods, and the agent releases payment upon confirmed delivery or resolves disputes.",
  },
  {
    label: "Trade Settlement",
    prompt: "I need a Delivery vs Payment (DvP) trade settlement contract for atomic settlement between hedge funds and investment banks through a central clearing house.",
  },
  {
    label: "NFT Marketplace",
    prompt: "Create an NFT ownership contract where artists can mint digital art tokens, set royalty rates, and collectors can buy, sell, and transfer NFTs on a marketplace with automatic royalty payments.",
  },
];

const CANTON_ENVIRONMENTS = [
  { value: "sandbox", label: "Canton Sandbox", desc: "Local development — instant, free" },
  { value: "devnet",  label: "Canton DevNet",  desc: "Public test network" },
  { value: "mainnet", label: "Canton MainNet", desc: "Production financial network" },
];

export default function HomePage() {
  const router = useRouter();
  const [prompt, setPrompt]                       = useState("");
  const [environment, setEnvironment]             = useState("sandbox");
  const [isGenerating, setIsGenerating]           = useState(false);
  const [charCount, setCharCount]                 = useState(0);

  const handlePromptChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setPrompt(e.target.value);
    setCharCount(e.target.value.length);
  };

  const handleExampleClick = (examplePrompt: string) => {
    setPrompt(examplePrompt);
    setCharCount(examplePrompt.length);
  };

  const handleGenerate = async () => {
    if (!prompt.trim() || prompt.length < 10) {
      toast.error("Please describe your contract in more detail.");
      return;
    }
    setIsGenerating(true);
    try {
      const response = await generateContract({
        prompt: prompt.trim(),
        canton_environment: environment as "sandbox" | "devnet" | "mainnet",
      });
      router.push(`/generate/${response.job_id}`);
    } catch {
      toast.error("Failed to start generation. Is the API server running?");
      setIsGenerating(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      handleGenerate();
    }
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-16">
      <div className="w-full max-w-3xl">

        {/* Hero */}
        <div className="text-center mb-12 animate-fade-in">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium mb-6" style={{ background: "rgba(90, 107, 255, 0.12)", color: "#818cf8", border: "1px solid rgba(90, 107, 255, 0.25)" }}>
            <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
            Powered by Claude + LangGraph + Canton Ledger API
          </div>
          <h1 className="text-5xl font-bold mb-4 leading-tight" style={{ color: "#e8eaf6" }}>
            Describe your contract.<br />
            <span style={{ background: "linear-gradient(135deg, #5a6bff, #818cf8)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
              We deploy it on-chain.
            </span>
          </h1>
          <p className="text-lg" style={{ color: "#9ca3af" }}>
            Ginie translates plain English into production-ready Daml smart contracts,<br />
            compiles them, auto-fixes errors, and deploys to Canton Network — automatically.
          </p>
        </div>

        {/* Main Card */}
        <div className="glass-card p-8 animate-slide-up" style={{ animationDelay: "0.1s" }}>

          {/* Textarea */}
          <div className="mb-5">
            <label className="block text-sm font-medium mb-2" style={{ color: "#9ca3af" }}>
              Describe your Canton contract
            </label>
            <div className="relative">
              <textarea
                value={prompt}
                onChange={handlePromptChange}
                onKeyDown={handleKeyDown}
                rows={6}
                placeholder={`"I want a bond tokenization contract where Goldman Sachs can issue bonds to pension fund investors with 5% annual coupon payments and full privacy controls..."`}
                className="w-full resize-none rounded-xl px-4 py-4 text-sm leading-relaxed transition-all duration-200"
                style={{
                  background:    "rgba(10, 13, 26, 0.6)",
                  border:        "1px solid rgba(30, 42, 74, 0.8)",
                  color:         "#e8eaf6",
                  outline:       "none",
                }}
                onFocus={e => (e.currentTarget.style.borderColor = "rgba(90, 107, 255, 0.5)")}
                onBlur={e  => (e.currentTarget.style.borderColor = "rgba(30, 42, 74, 0.8)")}
              />
              <div className="absolute bottom-3 right-3 text-xs" style={{ color: "#4b5563" }}>
                {charCount} chars &nbsp;·&nbsp; Ctrl+↵ to generate
              </div>
            </div>
          </div>

          {/* Examples */}
          <div className="mb-6">
            <p className="text-xs font-medium mb-2" style={{ color: "#6b7280" }}>QUICK EXAMPLES</p>
            <div className="flex flex-wrap gap-2">
              {CONTRACT_EXAMPLES.map((ex) => (
                <button
                  key={ex.label}
                  onClick={() => handleExampleClick(ex.prompt)}
                  className="text-xs px-3 py-1.5 rounded-lg transition-all duration-150"
                  style={{
                    background: "rgba(90, 107, 255, 0.08)",
                    color:      "#818cf8",
                    border:     "1px solid rgba(90, 107, 255, 0.2)",
                  }}
                  onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = "rgba(90, 107, 255, 0.15)"; }}
                  onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = "rgba(90, 107, 255, 0.08)"; }}
                >
                  {ex.label}
                </button>
              ))}
            </div>
          </div>

          {/* Environment Selector */}
          <div className="mb-6">
            <label className="block text-xs font-medium mb-2" style={{ color: "#6b7280" }}>CANTON ENVIRONMENT</label>
            <div className="grid grid-cols-3 gap-2">
              {CANTON_ENVIRONMENTS.map((env) => (
                <button
                  key={env.value}
                  onClick={() => setEnvironment(env.value)}
                  className="text-left p-3 rounded-xl transition-all duration-150"
                  style={{
                    background: environment === env.value ? "rgba(90, 107, 255, 0.15)" : "rgba(10, 13, 26, 0.6)",
                    border:     environment === env.value ? "1px solid rgba(90, 107, 255, 0.5)" : "1px solid rgba(30, 42, 74, 0.6)",
                  }}
                >
                  <div className="text-xs font-semibold mb-0.5" style={{ color: environment === env.value ? "#818cf8" : "#9ca3af" }}>
                    {env.label}
                  </div>
                  <div className="text-xs" style={{ color: "#4b5563" }}>{env.desc}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Generate Button */}
          <button
            onClick={handleGenerate}
            disabled={isGenerating || prompt.length < 10}
            className="btn-primary w-full py-4 rounded-xl text-sm font-semibold flex items-center justify-center gap-3 transition-all duration-200"
          >
            {isGenerating ? (
              <>
                <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Launching pipeline...
              </>
            ) : (
              <>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polygon points="5 3 19 12 5 21 5 3" />
                </svg>
                Generate &amp; Deploy Contract
              </>
            )}
          </button>
        </div>

        {/* How it works */}
        <div className="mt-12 grid grid-cols-5 gap-3 animate-fade-in" style={{ animationDelay: "0.3s" }}>
          {[
            { icon: "🧠", label: "Understand",  desc: "LLM parses intent" },
            { icon: "📚", label: "RAG Lookup",  desc: "Find Daml patterns" },
            { icon: "✍️", label: "Write Daml",  desc: "Generate contract code" },
            { icon: "⚙️", label: "Compile",     desc: "Run Daml SDK + auto-fix" },
            { icon: "🚀", label: "Deploy",       desc: "Upload DAR to Canton" },
          ].map((step, i) => (
            <div key={i} className="text-center">
              <div className="text-2xl mb-2">{step.icon}</div>
              <div className="text-xs font-semibold mb-1" style={{ color: "#e8eaf6" }}>{step.label}</div>
              <div className="text-xs" style={{ color: "#6b7280" }}>{step.desc}</div>
              {i < 4 && (
                <div className="hidden md:block absolute" />
              )}
            </div>
          ))}
        </div>

      </div>
    </div>
  );
}
