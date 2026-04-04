"use client";

import { useRef, useEffect, useState } from "react";
import type { ReactNode } from "react";

const headline =
  "Ginie transforms how teams build on Canton  describe your contract in plain English, and our AI generates production-ready DAML, compiles it with the SDK, runs a security audit, and deploys it live on the ledger in minutes.";

export function BlurInHeadline(): ReactNode {
  const containerRef = useRef<HTMLDivElement>(null);
  const [scrollProgress, setScrollProgress] = useState(0);
  const words = headline.split(" ");

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let ticking = false;

    const handleScroll = () => {
      if (ticking) return;
      ticking = true;

      requestAnimationFrame(() => {
        const rect = container.getBoundingClientRect();
        const windowHeight = window.innerHeight;
        
        const startOffset = windowHeight * 0.9;
        const endOffset = windowHeight * 0.25;
        
        const progress = Math.min(
          1,
          Math.max(0, (startOffset - rect.top) / (startOffset - endOffset))
        );
        
        setScrollProgress(progress);
        ticking = false;
      });
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();

    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <section
      ref={containerRef}
      className="w-full bg-black px-6 py-24"
    >
      <div className="mx-auto max-w-5xl">
        <p className="text-3xl font-medium text-center leading-snug tracking-tight text-white sm:text-4xl lg:text-5xl lg:leading-snug">
          {words.map((word, index) => {
            const wordStart = index / words.length;
            const wordEnd = wordStart + 1 / words.length;
            
            const wordProgress = Math.min(
              1,
              Math.max(0, (scrollProgress - wordStart) / (wordEnd - wordStart))
            );
            const opacity = 0.15 + wordProgress * 0.85;
            const blur = (1 - wordProgress) * 8;

            const plain = word.replace(/[^a-zA-Z]/g, "").toLowerCase();
            const isGinie = plain === "ginie";
            const spanStyle: any = {
              opacity,
              filter: `blur(${blur}px)`,
              transition: "opacity 75ms, filter 75ms",
            };
            if (isGinie) {
              spanStyle.color = "var(--accent)";
              spanStyle.fontFamily = "EB Garamond, serif";
            }

            return (
              <span
                key={index}
                className="mr-2 inline-block lg:mr-3"
                style={spanStyle}
              >
                {word}
              </span>
            );
          })}
        </p>
      </div>
    </section>
  );
}
