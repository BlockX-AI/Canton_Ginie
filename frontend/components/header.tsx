"use client";

import {
  motion,
  AnimatePresence,
  useScroll,
  useMotionValueEvent,
} from "motion/react";
import Image from "next/image";
import Link from "next/link";
import { useState, type ReactNode } from "react";

const navLinks = [
  { href: "#features", label: "Features" },
  { href: "#templates", label: "Templates" },
  { href: "#pricing", label: "Pricing" },
  { href: "#resources", label: "Resources" },
];

const authLinks = [
  { href: "", label: "Contact" },
  { href: "", label: "Join" },
];

export function Header(): ReactNode {
  const [isOpen, setIsOpen] = useState(false);
  const [isHidden, setIsHidden] = useState(false);
  const { scrollY } = useScroll();

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
              className="focus-ring flex items-center"
              aria-label="Kraft home"
            >
              <Image
                src="/svg/logo.svg"
                alt="Kraft"
                width={120}
                height={34}
                priority
              />
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
