"use client";

import { useRef, type ReactNode } from "react";
import { motion, useInView } from "motion/react";

interface Competitor {
  name: string;
  value: number;
  isKraft?: boolean;
}

interface Benchmark {
  category: string;
  metric: string;
  competitors: Competitor[];
}

const benchmarks: Benchmark[] = [
  {
    category: "Speed",
    metric: "Designs/min",
    competitors: [
      { name: "Kraft", value: 94.2, isKraft: true },
      { name: "Figma AI", value: 71.8 },
      { name: "Canva Magic", value: 68.4 },
      { name: "Framer AI", value: 58.7 },
    ],
  },
  {
    category: "Quality",
    metric: "Score",
    competitors: [
      { name: "Kraft", value: 96.8, isKraft: true },
      { name: "Figma AI", value: 89.2 },
      { name: "Canva Magic", value: 82.1 },
      { name: "Framer AI", value: 79.4 },
    ],
  },
  {
    category: "Consistency",
    metric: "Accuracy %",
    competitors: [
      { name: "Kraft", value: 98.1, isKraft: true },
      { name: "Figma AI", value: 81.3 },
      { name: "Framer AI", value: 76.9 },
      { name: "Canva Magic", value: 72.4 },
    ],
  },
];

function BarChart({ benchmark }: { benchmark: Benchmark }) {
  const ref = useRef<HTMLDivElement>(null);
  const isInView = useInView(ref, { once: true, margin: "-100px" });

  const maxValue = Math.max(...benchmark.competitors.map((c) => c.value));

  return (
    <div ref={ref} className="space-y-4">
      <div className="mb-6">
        <h3 className="text-lg font-medium text-foreground">
          {benchmark.category}
        </h3>
        {/* <p className="text-sm text-muted-foreground">( {benchmark.metric} )</p> */}
      </div>

      <div className="space-y-3">
        {benchmark.competitors.map((competitor, index) => {
          const percentage = (competitor.value / maxValue) * 100;

          return (
            <div key={competitor.name} className="flex items-center gap-4">
              <div className="w-28 shrink-0">
                <span
                  className={`text-sm ${
                    competitor.isKraft
                      ? "font-medium text-foreground"
                      : "text-muted-foreground"
                  }`}
                >
                  {competitor.name}
                </span>
              </div>

              <div className="flex flex-1 items-center gap-0">
                <div className="relative h-6 flex-1 overflow-hidden rounded-sm bg-muted/30">
                  <motion.div
                    className={`absolute inset-y-0 left-0 rounded-sm ${
                      competitor.isKraft
                        ? "bg-linear-to-r from-[#333DA7] to-[#7388DF]"
                        : "bg-muted/75"
                    }`}
                    initial={{ width: 0 }}
                    animate={isInView ? { width: `${percentage}%` } : { width: 0 }}
                    transition={{
                      duration: 0.8,
                      delay: index * 0.1,
                      ease: [0.25, 0.46, 0.45, 0.94],
                    }}
                  />
                </div>

                <div className="w-12 shrink-0 pl-2 text-right">
                  <motion.span
                    className={`text-sm tabular-nums ${
                      competitor.isKraft
                        ? "font-medium text-foreground"
                        : "text-muted-foreground"
                    }`}
                    initial={{ opacity: 0 }}
                    animate={isInView ? { opacity: 1 } : { opacity: 0 }}
                    transition={{ duration: 0.4, delay: 0.5 + index * 0.1 }}
                  >
                    {competitor.value}
                  </motion.span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function Stats(): ReactNode {
  return (
    <section className="px-4 py-20 sm:px-6 md:py-28 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <div className="mb-16 max-w-2xl">
          <h2 className="text-2xl font-medium tracking-tight text-foreground md:text-3xl lg:text-4xl">
            Performance that stands out
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            We benchmark Kraft against leading design tools across speed,
            quality, and consistency. The results speak for themselves.
          </p>
        </div>

        <div className="grid gap-12 lg:grid-cols-3 lg:gap-12">
          {benchmarks.map((benchmark) => (
            <BarChart key={benchmark.category} benchmark={benchmark} />
          ))}
        </div>
      </div>
    </section>
  );
}
