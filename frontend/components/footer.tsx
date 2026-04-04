"use client";

import HlsVideo from "./HlsVideo";
import { ArrowUpRight, Mail } from "lucide-react";
import type { ReactNode } from "react";

const HLS_SRC = "https://stream.mux.com/8wrHPCX2dC3msyYU9ObwqNdm00u3ViXvOSHUMRYSEe5Q.m3u8";

export function Footer(): ReactNode {
  return (
    <section id="pricing" className="relative w-full overflow-hidden">
      {/* HLS Background Video */}
      <HlsVideo src={HLS_SRC} className="absolute inset-0 w-full h-full object-cover z-0" />

      {/* Top fade */}
      <div
        className="absolute top-0 left-0 right-0 z-[1]"
        style={{ height: "200px", background: "linear-gradient(to bottom, black, transparent)" }}
      />

      {/* Bottom fade */}
      <div
        className="absolute bottom-0 left-0 right-0 z-[1]"
        style={{ height: "200px", background: "linear-gradient(to top, black, transparent)" }}
      />

      {/* Content */}
      <div className="relative z-10 flex flex-col items-center justify-center text-center py-32 px-6 md:px-16 lg:px-24 min-h-[600px]">
        <h2 className="text-5xl md:text-6xl lg:text-7xl font-heading italic text-white tracking-tight leading-[0.9] max-w-4xl" style={{ fontFamily: "EB Garamond, serif" }}>
         Start building on Canton today
        </h2>

        
        <div className="mt-10 w-full flex items-center justify-center">
          <form onSubmit={(e) => e.preventDefault()} className="flex items-center w-full max-w-md bg-white/5 rounded-xl p-1.5 border-t border-b border-white/10">
            <Mail className="w-5 h-5 text-white/60 ml-3 flex-none" aria-hidden="true" />
            <input
              type="email"
              placeholder="Enter your email"
              aria-label="Email address"
              className="flex-1 px-3 py-2 text-sm bg-transparent placeholder-white/60 text-white focus:outline-none"
            />
            <button
              type="submit"
              className="ml-3 flex items-center gap-2 px-4 py-2 bg-accent text-black rounded-lg text-sm font-medium transition-colors"
            >
              Join Waitlist
              <ArrowUpRight className="w-4 h-4" />
            </button>
          </form>
        </div>

        {/* Footer */}
        <footer className="mt-32 pt-8 border-t border-white/10 w-full max-w-4xl">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <span className="text-white/40 text-xs font-body">© 2026 Ginie DAML by BlockXAI. All rights reserved.</span>
            <div className="flex items-center gap-6">
              <a href="#" className="text-white/40 text-xs font-body hover:text-white/60 transition-colors">
                Privacy
              </a>
              <a href="#" className="text-white/40 text-xs font-body hover:text-white/60 transition-colors">
                Terms
              </a>
              <a href="#" className="text-white/40 text-xs font-body hover:text-white/60 transition-colors">
                Contact
              </a>
            </div>
          </div>
        </footer>
      </div>
    </section>
  );
}
