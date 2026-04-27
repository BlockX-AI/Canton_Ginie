"use client";

import { ArrowRight, Mail } from "lucide-react";
import Image from "next/image";
import type { ReactNode } from "react";

const footerLinks = {
  menu: [
    { label: "Documentation", href: "#" },
    { label: "Canton Network", href: "https://www.canton.network" },
    { label: "DAML Docs", href: "https://docs.daml.com" },
  ],
  company: [
    { label: "About BlockX", href: "https://blockxint.com/" },
    { label: "Terms", href: "https://blockxint.com/about/" },
  ],
  social: [
    { label: "GitHub", href: "https://github.com/BlockX-AI/Canton_Ginie" },
    { label: "X (Twitter)", href: "https://x.com/giniedev" },
  ],
};

export function Footer(): ReactNode {
  return (
    <footer className="relative pt-38 mt-24 mx-2.5 max-[850px]:mx-0">
      <div className="absolute left-1/2 -translate-x-1/2 top-0 w-full max-w-5xl">
        <div className="relative w-full rounded-3xl overflow-hidden shadow-2xl/15">
          <div 
            className="absolute inset-0 bg-center bg-no-repeat brightness-150 blur scale-125"
            style={{ backgroundImage: 'url(/BG.jpg)', backgroundSize: '150%' }}
            aria-hidden="true"
          />
          
          <div className="relative z-10 flex flex-col items-center text-center px-12 py-24 max-[850px]:px-6 max-[850px]:py-6 max-[850px]:pt-12">
            <h2 className="text-6xl max-[850px]:text-3xl text-black font-medium tracking-tight max-w-2xl mb-14 max-[850px]:mb-8">
              Start building on Canton today
            </h2>
            
            <form className="flex items-center w-full max-w-md bg-background rounded-xl p-1.5 shadow-lg max-[850px]:flex-col max-[850px]:p-3 max-[850px]:gap-3 max-[850px]:max-w-none">
              <div className="flex items-center flex-1 w-full">
                <Mail className="w-5 h-5 text-muted-foreground ml-3 flex-none max-[850px]:ml-1" aria-hidden="true" />
                <input
                  type="email"
                  placeholder="Enter your email"
                  aria-label="Email address"
                  className="flex-1 px-3 py-2.5 text-sm bg-transparent text-foreground placeholder:text-muted-foreground focus:outline-none"
                />
              </div>
              <button
                type="submit"
                className="flex items-center justify-center gap-2 px-5 py-2.5 bg-foreground hover:bg-foreground/90 text-background rounded-lg text-sm font-medium transition-colors whitespace-nowrap max-[850px]:w-full max-[850px]:py-3"
              >
                Join Waitlist
                <ArrowRight className="w-4 h-4" aria-hidden="true" />
              </button>
            </form>
          </div>
        </div>
      </div>

      <div className="bg-accent rounded-tr-[3rem] rounded-tl-[3rem] pt-96 pb-16 max-[850px]:pt-72">
        <div className="max-w-5xl mx-auto px-6">
          <div className="flex items-start justify-between gap-12 max-[850px]:flex-col max-[850px]:gap-10">
            <a href="/" className="flex items-center gap-2" aria-label="Ginie DAML home">
              <span className="flex h-8 w-8 items-center justify-center overflow-hidden rounded-full bg-neutral-900">
                <Image
                  src="/ginie-logo.ico"
                  alt="Ginie"
                  width={24}
                  height={24}
                  unoptimized
                  className="h-6 w-6 object-contain"
                />
              </span>
              <span className="text-xl font-semibold text-neutral-900 leading-0">Ginie</span>
            </a>

            <nav className="flex gap-16 max-[850px]:gap-10 max-[850px]:flex-wrap" aria-label="Footer navigation">
              {([
                { title: "Menu", items: footerLinks.menu },
                { title: "Company", items: footerLinks.company },
                { title: "Social", items: footerLinks.social },
              ] as const).map((col) => (
                <div key={col.title}>
                  <h3 className="text-xs font-medium text-neutral-900/50 uppercase tracking-wider mb-4">{col.title}</h3>
                  <ul className="space-y-2">
                    {col.items.map((link) => {
                      const isExternal = link.href.startsWith("http");
                      return (
                        <li key={link.label}>
                          <a
                            href={link.href}
                            className="text-sm text-neutral-900 hover:text-neutral-900/70 transition-colors"
                            {...(isExternal
                              ? { target: "_blank", rel: "noopener noreferrer" }
                              : {})}
                          >
                            {link.label}
                          </a>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ))}
            </nav>
          </div>

          <div className="mt-16 pt-6 space-y-2">
            <p className="text-xs text-neutral-900/60 text-center">
              Canton.Ginie is an AI and can make mistakes. Check important info before deploying to a production network.
            </p>
            <p className="text-sm text-neutral-900/50 text-center">
              © {new Date().getFullYear()} Ginie DAML by BlockXAI. All rights reserved.
            </p>
          </div>
        </div>
      </div>
    </footer>
  );
}
