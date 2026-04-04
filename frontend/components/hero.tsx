"use client";

import { motion } from "motion/react";
import { ArrowUpRight } from "lucide-react";
import Link from "next/link";
import BlurText from "./BlurText";
import { ReactNode, useEffect, useState } from "react";

const HERO_POSTER = "https://d2xsxph8kpxj0f.cloudfront.net/310419663030385168/MC3Zr7iXaECD86HNQzfZgw/hero_bg-eZYaAXXw7EFgUwJKSAykrT.webp";
const HERO_VIDEO = "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260307_083826_e938b29f-a43a-41ec-a153-3d4730578ab8.mp4";

export function Hero(): ReactNode {
  return (
    <section id="home" className="relative overflow-visible bg-black" style={{ height: "1000px" }}>
      {/* Background Video */}
      <video
        className="absolute top-[20%] w-full h-auto object-contain z-0"
        src={HERO_VIDEO}
        poster={HERO_POSTER}
        autoPlay
        loop
        muted
        playsInline
      />

      {/* Light darkening overlay */}
      <div className="absolute inset-0 bg-black/5 z-0" />

      {/* Bottom gradient fade */}
      <div
        className="absolute bottom-0 left-0 right-0 z-[1]"
        style={{
          height: "300px",
          background: "linear-gradient(to bottom, transparent, black)",
        }}
      />

      {/* Content */}
      <div className="relative z-10 flex flex-col items-center text-center h-full" style={{ paddingTop: "150px" }}>
        {/* Badge */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="liquid-glass rounded-full px-1.5 py-1 flex items-center gap-2 mb-8"
        >
          <span className="bg-white text-black rounded-full px-2.5 py-0.5 text-xs font-medium font-body">
            Canton
          </span>
          <span className="text-white/80 text-sm font-body font-light pr-3">
            Network
          </span>
        </motion.div>

        {/* Heading */}
        <div className="max-w-5xl mx-auto px-4" style={{ fontFamily: "EB Garamond, serif" }}>
          <BlurText
            text="From Idea to
Canton in Minutes"
            className="text-6xl md:text-7xl lg:text-[5.5rem] font-heading italic text-white leading-[0.8] tracking-[-4px]"
            delay={100}
          />
        </div>

        {/* Subtext */}
        <motion.p
          initial={{ opacity: 0, filter: "blur(10px)" }}
          animate={{ opacity: 1, filter: "blur(0px)" }}
          transition={{ duration: 0.6, delay: 0.8 }}
          className="mt-8 max-w-xl mx-auto text-white/60 font-body font-light text-sm md:text-base px-4 leading-relaxed"
        >
          Describe your smart contract in plain English. Ginie generates production-ready DAML, compiles it, audits it, and deploys it to Canton. 
        </motion.p>

        {/* CTA Buttons */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 1.1 }}
          className="flex items-center gap-4 mt-10"
        >
          <Link
            href="/setup"
            className="liquid-glass-strong rounded-full px-7 py-3 text-sm font-medium font-body text-white flex items-center gap-2 border-t border-b border-white/30 hover:bg-white/3 transition-colors"
          >
            Add parties
            <ArrowUpRight className="w-4 h-4" />
          </Link>
          
        </motion.div>

        {/* Partners bar pushed to bottom */}
        <div className="mt-auto pb-8 pt-16 w-full">
            <Partners />
          </div>
      </div>
    </section>
  );
}

function Partners() {
  const partners = ["Canton Network", "DAML", "GPT 4o", "Chroma DB", "Postgress SQL", "Lang Graph", "Digital Assets"];
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setIndex((i) => (i + 2) % partners.length), 2000);
    return () => clearInterval(t);
  }, [partners.length]);

  return (
    <div className="flex flex-col items-center gap-4">
      <span className="liquid-glass-strong rounded-full px-6 py-1 text-sm font-small font-body text-white flex items-center gap-2 border-t border-b border-white/30 hover:bg-white/3 transition-colors">
        Features of{" "}
        <span style={{ fontFamily: "EB Garamond, serif" }}>
          Ginie
        </span>
        {" "}canton
      </span>

      <div className="w-full flex items-center justify-center h-12">
        <motion.div
          key={index}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
          className="flex items-center gap-8"
        >
          <span
            className="text-2xl md:text-3xl font-heading italic text-white"
            style={{ fontFamily: "EB Garamond, serif" }}
          >
            {partners[index]}
          </span>
          <span
            className="text-2xl md:text-3xl font-heading italic text-white"
            style={{ fontFamily: "EB Garamond, serif" }}
          >
            {partners[(index + 1) % partners.length]}
          </span>
        </motion.div>
      </div>
    </div>
  );
}
