"use client";

import { ReducedMotionProvider } from "@/lib/motion";
import { SmoothScroll } from "@/components/smooth-scroll";
import { AuthProvider } from "@/lib/auth-context";
import { AuthGate } from "@/components/auth-gate";
import { ThemeProvider } from "next-themes";
import type { ReactNode } from "react";

export function Providers({ children }: { children: ReactNode }): ReactNode {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
    >
      <AuthProvider>
        <ReducedMotionProvider>
          <SmoothScroll>
            <AuthGate>{children}</AuthGate>
          </SmoothScroll>
        </ReducedMotionProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
