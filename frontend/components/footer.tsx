"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import Image from "next/image";
import { Facebook, Twitter, Linkedin } from "lucide-react";

const footerLinks = {
  Product: [
    { label: "Features", href: "#" },
    { label: "Pricing", href: "#" },
    { label: "Changelog", href: "#" },
    { label: "Roadmap", href: "#" },
  ],
  Company: [
    { label: "About", href: "#" },
    { label: "Blog", href: "#" },
    { label: "Careers", href: "#" },
    { label: "Press", href: "#" },
  ],
  Resources: [
    { label: "Documentation", href: "#" },
    { label: "Help Center", href: "#" },
    { label: "Community", href: "#" },
  ],
};

const socialLinks = [
  { icon: Facebook, href: "#", label: "Facebook" },
  { icon: Twitter, href: "#", label: "Twitter" },
  { icon: Linkedin, href: "#", label: "LinkedIn" },
];

export function Footer(): ReactNode {
  return (
    <footer className="relative overflow-hidden bg-background px-4 text-foreground sm:px-6 lg:px-8">
      <div
        className="pointer-events-none absolute inset-x-0 bottom-0 h-2/3 opacity-60"
        style={{
          background:
            "linear-gradient(to top, rgba(51,61,167,0.8) 0%, rgba(81,96,195,0.5) 20%, rgba(115,136,223,0.3) 40%, rgba(140,158,230,0.15) 60%, rgba(165,180,240,0.05) 80%, transparent 100%)",
          maskImage:
            "linear-gradient(to top, black 0%, black 20%, transparent 100%)",
          WebkitMaskImage:
            "linear-gradient(to top, black 0%, black 20%, transparent 100%)",
        }}
        aria-hidden="true"
      />
      <div className="relative mx-auto max-w-7xl py-16">
        <div className="flex flex-col gap-12 lg:flex-row lg:justify-between">
          <div className="grid flex-1 gap-8 sm:grid-cols-3">
            {Object.entries(footerLinks).map(([category, links]) => (
              <div key={category}>
                <h3 className="text-sm text-muted-foreground">{category}</h3>
                <ul className="mt-4 space-y-3">
                  {links.map((link) => (
                    <li key={link.label}>
                      <Link
                        href={link.href}
                        className="text-lg text-foreground transition-colors hover:text-foreground/70"
                      >
                        {link.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          <div className="lg:text-right">
            <h3 className="text-sm text-muted-foreground">Social</h3>
            <div className="mt-4 flex gap-3 lg:justify-end">
              {socialLinks.map((social) => (
                <Link
                  key={social.label}
                  href={social.href}
                  className="flex h-11 w-11 items-center justify-center rounded-full bg-foreground/10 text-foreground transition-colors hover:bg-foreground/20"
                  aria-label={social.label}
                >
                  <social.icon className="h-5 w-5 fill-foreground/40 text-foreground/40" strokeWidth={1} />
                </Link>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="relative mx-auto max-w-7xl py-8">
        <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
          <p className="text-sm text-muted-foreground">
            © {new Date().getFullYear()} Kraft, Inc. All rights reserved.
          </p>
          <div className="flex gap-6">
            <Link
              href="#"
              className="text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              Terms
            </Link>
            <Link
              href="#"
              className="text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              Privacy
            </Link>
            <Link
              href="#"
              className="text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              Cookies
            </Link>
          </div>
        </div>
      </div>

      <div className="relative mx-auto max-w-338 select-none h-44 pb-12">
        <Image
          src="/svg/logo-text.svg"
          alt=""
          width={2500}
          height={400}
          className="w-full opacity-5 invert dark:invert-0"
          aria-hidden="true"
        />
      </div>
    </footer>
  );
}
