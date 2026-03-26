"use client";

import {
  motion,
  AnimatePresence,
  useScroll,
  useMotionValueEvent,
} from "motion/react";
import Link from "next/link";
import { useState, type ReactNode } from "react";
import { useAuth } from "@/lib/auth-context";

const navLinks = [
  { href: "#features", label: "Features" },
  { href: "#how-it-works", label: "How It Works" },
  { href: "#pricing", label: "Pricing" },
  { href: "#faq", label: "FAQ" },
];

const authLinks = [
  { href: "https://github.com/Satyam-10124/Ginie_Daml", label: "GitHub" },
  { href: "#", label: "Docs" },
];

export function Header(): ReactNode {
  const [isOpen, setIsOpen] = useState(false);
  const [isHidden, setIsHidden] = useState(false);
  const { scrollY } = useScroll();
  const { isAuthenticated, displayName, partyId, logout } = useAuth();

  useMotionValueEvent(scrollY, "change", (latest) => {
    const previous = scrollY.getPrevious() ?? 0;

    if (latest > previous && latest > 50) {
      setIsHidden(true);
    } else {
      setIsHidden(false);
    }
  });

  const toggleMenu = () => setIsOpen(!isOpen);
  const closeMenu = () => setIsOpen(false);

  return (
    <>
      <div
        className="pointer-events-none fixed top-0 left-0 z-40 h-32 w-full"
        style={{
          backdropFilter: "blur(12px)",
          WebkitBackdropFilter: "blur(12px)",
          maskImage:
            "linear-gradient(to bottom, black 0%, black 20%, rgba(0,0,0,0.8) 40%, rgba(0,0,0,0.4) 60%, rgba(0,0,0,0.1) 80%, transparent 100%)",
          WebkitMaskImage:
            "linear-gradient(to bottom, black 0%, black 20%, rgba(0,0,0,0.8) 40%, rgba(0,0,0,0.4) 60%, rgba(0,0,0,0.1) 80%, transparent 100%)",
        }}
        aria-hidden="true"
      />

      <motion.header
        className="fixed top-0 z-50 w-full mix-blend-difference"
        initial={{ y: -20, opacity: 0, filter: "blur(10px)" }}
        animate={{
          y: isHidden && !isOpen ? "-100%" : 0,
          opacity: 1,
          filter: isHidden && !isOpen ? "blur(8px)" : "blur(0px)",
        }}
        transition={{ duration: 0.6, ease: [0.25, 0.46, 0.45, 0.94] }}
      >
        <div className="mx-auto flex h-24 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{
              duration: 0.5,
              delay: 0.1,
              ease: [0.25, 0.46, 0.45, 0.94],
            }}
          >
            <Link
              href="/"
              className="focus-ring flex items-center gap-2"
              aria-label="Ginie DAML home"
            >
              <span className="text-2xl font-bold tracking-tight text-white">
                Ginie<span className="text-purple-400">.</span>
              </span>
            </Link>
          </motion.div>

          <nav
            className="hidden items-center gap-3 lg:flex"
            aria-label="Main navigation"
          >
            {navLinks.map((link, index) => (
              <motion.div
                key={link.href}
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{
                  duration: 0.4,
                  delay: 0.15 + index * 0.05,
                  ease: [0.25, 0.46, 0.45, 0.94],
                }}
              >
                <Link
                  href={link.href}
                  className="focus-ring rounded-md px-2.5 py-1 font-medium text-white transition-colors hover:bg-white/10 hover:text-white"
                >
                  {link.label}
                </Link>
              </motion.div>
            ))}

            <motion.div
              className="mx-4 h-px w-5 bg-white/30"
              role="separator"
              aria-orientation="vertical"
              initial={{ opacity: 0, scaleX: 0 }}
              animate={{ opacity: 1, scaleX: 1 }}
              transition={{ duration: 0.4, delay: 0.4, ease: "easeOut" }}
            />

            {authLinks.map((link, index) => (
              <motion.div
                key={link.label}
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{
                  duration: 0.4,
                  delay: 0.45 + index * 0.05,
                  ease: [0.25, 0.46, 0.45, 0.94],
                }}
              >
                <Link
                  href={link.href}
                  className="focus-ring rounded-md px-2.5 py-1 font-medium text-white transition-colors hover:bg-white/10 hover:text-white"
                >
                  {link.label}
                </Link>
              </motion.div>
            ))}

            <motion.div
              className="mx-4 h-px w-5 bg-white/30"
              role="separator"
              aria-orientation="vertical"
              initial={{ opacity: 0, scaleX: 0 }}
              animate={{ opacity: 1, scaleX: 1 }}
              transition={{ duration: 0.4, delay: 0.55, ease: "easeOut" }}
            />

            {isAuthenticated ? (
              <motion.div
                className="flex items-center gap-2"
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.6 }}
              >
                <span className="inline-flex items-center gap-1.5 rounded-full border border-green-500/30 bg-green-500/10 px-3 py-1 text-xs font-medium text-green-400">
                  <span className="h-1.5 w-1.5 rounded-full bg-green-400" />
                  {displayName || partyId?.split("::")[0] || "Connected"}
                </span>
                <button
                  onClick={() => logout()}
                  className="focus-ring rounded-md px-2 py-1 text-xs text-white/40 transition-colors hover:text-white/70"
                >
                  Logout
                </button>
              </motion.div>
            ) : (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.6 }}
              >
                <Link
                  href="/setup"
                  className="focus-ring inline-flex items-center gap-1.5 rounded-full border border-purple-500/30 bg-purple-500/10 px-3 py-1 text-xs font-medium text-purple-300 transition-colors hover:border-purple-500/50 hover:bg-purple-500/20"
                >
                  Set Up Identity
                </Link>
              </motion.div>
            )}
          </nav>

          <button
            type="button"
            onClick={toggleMenu}
            className="focus-ring relative flex h-10 w-10 items-center justify-center lg:hidden"
            aria-label={isOpen ? "Close menu" : "Open menu"}
            aria-expanded={isOpen}
          >
            <span className="sr-only">
              {isOpen ? "Close menu" : "Open menu"}
            </span>
            <span
              className={`absolute h-0.5 w-5 bg-white transition-transform duration-300 ${
                isOpen ? "rotate-45" : "rotate-0"
              }`}
            />
            <span
              className={`absolute h-5 w-0.5 bg-white transition-transform duration-300 ${
                isOpen ? "rotate-45" : "rotate-0"
              }`}
            />
          </button>
        </div>
      </motion.header>

      <AnimatePresence mode="sync">
        {isOpen && (
          <motion.div
            key="mobile-menu"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-40 bg-black/95 backdrop-blur-xl lg:hidden"
          >
            <nav
              className="mx-auto flex h-full max-w-7xl flex-col items-start gap-4 px-4 pt-32 sm:px-6"
              aria-label="Mobile navigation"
            >
              {navLinks.map((link, index) => (
                <motion.div
                  key={link.href}
                  initial={{ opacity: 0, x: -40, filter: "blur(10px)" }}
                  animate={{ opacity: 1, x: 0, filter: "blur(0px)" }}
                  transition={{
                    duration: 0.4,
                    delay: 0.05 + index * 0.08,
                    ease: [0.25, 0.46, 0.45, 0.94],
                  }}
                >
                  <Link
                    href={link.href}
                    onClick={closeMenu}
                    className="focus-ring block text-6xl text-white transition-colors hover:text-white sm:text-6xl"
                  >
                    {link.label}
                  </Link>
                </motion.div>
              ))}

              <motion.div
                initial={{ opacity: 0, scaleX: 0 }}
                animate={{ opacity: 1, scaleX: 1 }}
                transition={{ duration: 0.5, delay: 0.4, ease: "easeOut" }}
                className="my-4 h-px w-20 origin-left bg-white/30"
                role="separator"
              />

              {authLinks.map((link, index) => (
                <motion.div
                  key={link.label}
                  initial={{ opacity: 0, x: -40, filter: "blur(10px)" }}
                  animate={{ opacity: 1, x: 0, filter: "blur(0px)" }}
                  transition={{
                    duration: 0.4,
                    delay: 0.45 + index * 0.08,
                    ease: [0.25, 0.46, 0.45, 0.94],
                  }}
                >
                  <Link
                    href={link.href}
                    onClick={closeMenu}
                    className="focus-ring block text-6xl text-white transition-colors hover:text-white sm:text-6xl"
                  >
                    {link.label}
                  </Link>
                </motion.div>
              ))}
            </nav>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
