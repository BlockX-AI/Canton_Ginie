"use client";

import { useScroll, useTransform, useSpring, motion } from "motion/react";
import {
  Paperclip,
  Lightbulb,
  PenTool,
  Layout,
  Mic,
  ArrowRight,
  ArrowDown,
} from "lucide-react";
import Image from "next/image";
import { useRef, type ReactNode } from "react";
import { FluidCursor } from "./fluid-cursor";

export function Hero(): ReactNode {
  const sectionRef = useRef<HTMLElement>(null);

  const { scrollY, scrollYProgress } = useScroll({
    target: sectionRef,
    offset: ["start start", "end start"],
  });

  const scaleYRaw = useTransform(scrollYProgress, [0.0, 0.5], [1, 0]);
  const scaleY = useSpring(scaleYRaw, { stiffness: 100, damping: 30 });

  const y = useTransform(scrollY, (value) => value * 0.7);

  return (
    <section ref={sectionRef} className="relative min-h-dvh w-full">
      <FluidCursor className="absolute inset-0 -z-5" />

      <motion.div
        className="pointer-events-none absolute inset-0 -z-10 origin-top scale-125 will-change-transform"
        style={{ scaleY, y }}
        aria-hidden="true"
      >
        <Image
          src="/svg/gradient-fade.svg"
          alt=""
          fill
          className="object-cover object-top dark:-scale-y-100"
          priority
        />
        <div className="from-background absolute inset-x-0 bottom-0 h-1/3 bg-linear-to-t to-transparent" />
      </motion.div>

      <div className="mx-auto flex min-h-dvh max-w-4xl flex-col items-start justify-center gap-6 px-4 py-20 sm:justify-start sm:gap-0 sm:py-0 sm:pt-40 lg:px-8 lg:pt-68">
        <motion.h1
          className="text-background dark:text-background text-4xl font-medium tracking-tight sm:text-5xl md:text-6xl lg:text-7xl"
          initial={{ opacity: 0, y: 20, filter: "blur(8px)" }}
          animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          transition={{ duration: 0.6, ease: [0.25, 0.46, 0.45, 0.94] }}
        >
          <span className="block">Design with AI —</span>
          <span className="block">
            the{" "}
            <em className="text-background/80 dark:text-background/80 italic">
              future
            </em>{" "}
            of creativity
          </span>
        </motion.h1>

        <motion.div
          className="w-full sm:mt-12 lg:mt-16"
          initial={{ opacity: 0, y: 30, filter: "blur(8px)" }}
          animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          transition={{
            duration: 0.6,
            delay: 0.15,
            ease: [0.25, 0.46, 0.45, 0.94],
          }}
        >
          <div
            className="relative rounded-4xl rounded-b-[2.3rem] border border-black/5 bg-[#f8f8fa] p-3"
            style={{
              boxShadow:
                "0 8px 32px rgba(0, 0, 0, 0.1), 0 4px 16px rgba(124, 58, 237, 0.08)",
            }}
          >
            <div className="flex items-start gap-3">
              <textarea
                placeholder="Ask Kraft anything..."
                className="no-focus-ring mx-4 my-2 min-h-15 w-full resize-none bg-transparent text-gray-800 placeholder:text-gray-400"
                rows={2}
              />
            </div>

            <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  className="focus-ring isolate flex h-12 w-12 shrink-0 cursor-pointer items-center justify-center rounded-full bg-white text-gray-400 transition-colors hover:border-gray-300 hover:text-gray-600"
                  aria-label="Attach file"
                >
                  <Paperclip className="h-4 w-4" />
                </button>

                <button
                  type="button"
                  className="focus-ring isolate flex h-12 shrink-0 cursor-pointer items-center gap-2 rounded-full bg-white px-5 text-sm text-gray-500 transition-colors hover:border-gray-300 hover:text-gray-700"
                >
                  <Lightbulb className="h-4 w-4 shrink-0" />
                  <span className="xs:inline hidden">Reasoning</span>
                </button>

                <button
                  type="button"
                  className="focus-ring isolate hidden h-12 shrink-0 cursor-pointer items-center gap-2 rounded-full bg-white px-5 text-sm text-gray-500 transition-colors hover:border-gray-300 hover:text-gray-700 sm:flex"
                >
                  <PenTool className="h-4 w-4 shrink-0" />
                  <span>Create Design</span>
                </button>

                <button
                  type="button"
                  className="focus-ring isolate hidden h-12 shrink-0 cursor-pointer items-center gap-2 rounded-full bg-white px-5 text-sm text-gray-500 transition-colors hover:border-gray-300 hover:text-gray-700 md:flex"
                >
                  <Layout className="h-4 w-4 shrink-0" />
                  <span>Wireframe</span>
                </button>
              </div>

              <div className="flex shrink-0 items-center gap-2">
                <button
                  type="button"
                  className="focus-ring isolate hidden h-12 w-12 cursor-pointer items-center justify-center rounded-full bg-white text-gray-500 transition-colors hover:bg-gray-300 hover:text-gray-700 sm:flex"
                  aria-label="Voice input"
                >
                  <Mic className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  className="focus-ring bg-foreground dark:bg-background hover:bg-foreground/90 dark:hover:bg-background/90 isolate flex h-12 w-12 cursor-pointer items-center justify-center rounded-full text-white transition-colors"
                  aria-label="Send message"
                >
                  <ArrowRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>

          <p className="text-background/60 mt-6 text-center text-xs">
            Kraft can make mistakes, but learns from them.
          </p>
        </motion.div>
      </div>

      <motion.div
        className="absolute inset-x-0 bottom-24 mx-auto flex max-w-4xl items-center justify-between px-4 sm:px-6 lg:px-8"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{
          duration: 0.5,
          delay: 0.4,
          ease: [0.25, 0.46, 0.45, 0.94],
        }}
      >
        <p className="text-foreground/60 dark:text-foreground/50 max-w-sm text-sm">
          Kraft uses advanced AI to transform your ideas into stunning designs.
          Just describe what you need.
        </p>

        <ArrowDown
          className="text-foreground/60 dark:text-foreground/50 h-12 w-12"
          strokeWidth={1}
        />
      </motion.div>
    </section>
  );
}
