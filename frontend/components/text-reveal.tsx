"use client";

import { useRef, type ReactNode } from "react";
import { motion, useScroll, useTransform } from "motion/react";

interface TextRevealProps {
  text: string;
  className?: string;
}

function mapRange(
  inMin: number,
  inMax: number,
  outMin: number,
  outMax: number,
  value: number
): number {
  if (inMax === inMin) return outMin;
  return outMin + ((value - inMin) * (outMax - outMin)) / (inMax - inMin);
}

function getFactor(position: number, charsTotal: number): number {
  const mid = Math.ceil(charsTotal / 2);
  if (position < mid) {
    return position;
  }
  return mid - Math.abs(Math.floor(charsTotal / 2) - position) - 1;
}

function Char({
  char,
  charIndex,
  charsTotal,
  progress,
}: {
  char: string;
  charIndex: number;
  charsTotal: number;
  progress: ReturnType<typeof useScroll>["scrollYProgress"];
}): ReactNode {
  const factor = getFactor(charIndex, charsTotal);
  const mid = Math.ceil(charsTotal / 2);

  const initialScale = mapRange(0, mid, 0.5, 2.1, factor);
  const initialY = mapRange(0, mid, 0, 60, factor);
  const initialRotation =
    charIndex < charsTotal / 2
      ? mapRange(0, mid, -4, 0, factor)
      : mapRange(0, mid, 0, 4, factor);

  const normalizedPosition = charsTotal > 1 ? charIndex / (charsTotal - 1) : 0;

  const staggerAmount = 0.5;
  const charStartDelay = normalizedPosition * staggerAmount;

  const adjustedProgress = useTransform(progress, (p) => {
    const start = charStartDelay;
    const end = 1;
    const range = end - start;
    if (range <= 0) return p;
    return Math.max(0, Math.min(1, (p - start) / range));
  });

  const easedProgress = useTransform(adjustedProgress, (p) => {
    if (p <= 0) return 0;
    if (p >= 1) return 1;
    return p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
  });

  const scale = useTransform(easedProgress, [0, 1], [initialScale, 1]);
  const y = useTransform(easedProgress, [0, 1], [initialY, 0]);
  const rotate = useTransform(easedProgress, [0, 1], [initialRotation, 0]);
  const blur = useTransform(easedProgress, [0, 1], [12, 0]);
  const opacity = useTransform(easedProgress, [0, 1], [0, 1]);

  const filter = useTransform(blur, (b) => `blur(${b}px)`);

  return (
    <motion.span
      className="inline-block will-change-transform"
      style={{
        scale,
        y,
        rotate,
        filter,
        opacity,
        transformOrigin: "50% 100%",
      }}
    >
      {char === " " ? "\u00A0" : char}
    </motion.span>
  );
}

export function TextReveal({
  text,
  className = "",
}: TextRevealProps): ReactNode {
  const containerRef = useRef<HTMLDivElement>(null);

  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start 1.4", "start 0.15"],
  });

  const chars = text.split("");
  const charsTotal = chars.length;

  return (
    <div
      ref={containerRef}
      className="flex min-h-64 items-center justify-center overflow-hidden px-8"
    >
      <p className={`text-center px-8 ${className}`}>
        {chars.map((char, index) => (
          <Char
            key={index}
            char={char}
            charIndex={index}
            charsTotal={charsTotal}
            progress={scrollYProgress}
          />
        ))}
      </p>
    </div>
  );
}
