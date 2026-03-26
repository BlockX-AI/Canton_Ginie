"use client";

import { SmoothScroll } from "@/components/smooth-scroll";
import { ReducedMotionProvider } from "@/lib/motion";
import { AuthProvider } from "@/lib/auth-context";
import { ThemeProvider } from "next-themes";
import type { ReactNode } from "react";

export function Providers({ children }: { children: ReactNode }): ReactNode {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem
      disableTransitionOnChange
    >
      <AuthProvider>
        <ReducedMotionProvider>
          <SmoothScroll>{children}</SmoothScroll>
        </ReducedMotionProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
