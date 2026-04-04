"use client";

import HlsVideo from "./HlsVideo";
import type { ReactNode } from "react";

const HLS_SRC = "https://stream.mux.com/NcU3HlHeF7CUL86azTTzpy3Tlb00d6iF3BmCdFslMJYM.m3u8";


export function Stats(): ReactNode {
  return (
    <section className="relative w-full overflow-hidden py-32">
      {/* HLS Background Video — desaturated */}
      <HlsVideo
        src={HLS_SRC}
        className="absolute inset-0 w-full h-full object-cover z-0"
        style={{ filter: "saturate(0)" }}
      />

      {/* Top fade */}
      <div
        className="absolute top-0 left-0 right-0 z-[1]"
        style={{
          height: "200px",
          background: "linear-gradient(to bottom, black, transparent)",
        }}
      />

      {/* Bottom fade */}
      <div
        className="absolute bottom-0 left-0 right-0 z-[1]"
        style={{
          height: "200px",
          background: "linear-gradient(to top, black, transparent)",
        }}
      />

      
      
    </section>
  );
}

export default Stats;
