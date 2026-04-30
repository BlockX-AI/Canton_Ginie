"use client";

import { Mail, ShieldCheck, UserCircle2, Check } from "lucide-react";
import type { ReactNode } from "react";

const STEPS = [
  { icon: Mail, label: "Email" },
  { icon: ShieldCheck, label: "Verify" },
  { icon: UserCircle2, label: "Profile" },
] as const;

export type SignupStepIndex = 0 | 1 | 2;

interface SignupStepperProps {
  current: SignupStepIndex;
}

export function SignupStepper({ current }: SignupStepperProps): ReactNode {
  return (
    <div className="flex items-center justify-center gap-1.5 sm:gap-2 mb-6">
      {STEPS.map((step, i) => {
        const Icon = step.icon;
        const isDone = i < current;
        const isActive = i === current;
        return (
          <div key={i} className="flex items-center gap-1.5 sm:gap-2">
            <div
              className={`
                flex items-center gap-2 transition-all
                ${isActive ? "scale-105" : ""}
              `}
            >
              <div
                className={`
                  h-8 w-8 sm:h-9 sm:w-9 rounded-full flex items-center justify-center border transition-all
                  ${isDone
                    ? "border-accent/60 bg-accent/15 text-accent"
                    : isActive
                      ? "border-accent bg-accent/15 text-accent shadow-[0_0_0_4px_rgba(163,230,53,0.08)]"
                      : "border-border bg-muted text-muted-foreground"
                  }
                `}
              >
                {isDone ? (
                  <Check className="h-4 w-4" strokeWidth={3} />
                ) : (
                  <Icon className="h-4 w-4" />
                )}
              </div>
              <span
                className={`
                  hidden sm:inline text-xs font-medium tracking-wide uppercase transition-colors
                  ${isActive ? "text-foreground" : isDone ? "text-accent" : "text-muted-foreground"}
                `}
              >
                {step.label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div
                className={`
                  h-px w-6 sm:w-8 transition-colors
                  ${isDone ? "bg-accent/40" : "bg-border"}
                `}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
