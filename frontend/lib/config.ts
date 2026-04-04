/**
 * ============================================================================
 * SITE CONFIGURATION
 * ============================================================================
 * 
 * Customize your landing page by editing the values below.
 * All text, links, and settings are centralized here for easy editing.
 */

export const siteConfig = {
  // Brand
  name: "Ginie DAML",
  tagline: "From Idea to Canton in Minutes",
  description: "AI-powered DAML contract generation and deployment on Canton Network",
  
  // URLs
  url: "https://ginie.dev",
  twitter: "@GinieDaml",
  
  // Navigation
  nav: {
    cta: {
      text: "Launch App",
      href: "/",
    },
    signIn: {
      text: "Sign in",
      href: "/setup",
    },
  },
};

export const heroConfig = {
  badge: "Canton Network",
  headline: {
    line1: "From Idea to",
    line2: "",
    accent: "Canton",
  },
  subheadline: "Describe your smart contract in plain English. Ginie generates production-ready DAML, compiles it, audits it, and deploys it to Canton — in minutes.",
  cta: {
    text: "Add Parties",
    href: "/setup",
  },
};

export const blurHeadlineConfig = {
  text: "Enterprise teams use Ginie to turn business logic into verified DAML contracts, leveraging AI-powered code generation with cryptographic identity and persistent deployment on Canton Network.",
};

export const testimonialsConfig = {
  title: "Built for Canton developers",
  autoplayInterval: 10000, // milliseconds
};

export const howItWorksConfig = {
  title: "How it works",
  description: "From a plain-English prompt to a deployed contract on Canton — here's the pipeline.",
  cta: {
    text: "Try it now",
    href: "/",
  },
};

export const pricingConfig = {
  title: "Simple, transparent pricing",
  description: "Start free on sandbox. Scale to DevNet and MainNet when you're ready.",
  billingNote: "Billed annually",
};

export const faqConfig = {
  title: "Everything you need to know",
  description: "Can't find the answer you're looking for? Reach out!",
  cta: {
    primary: {
      text: "Launch App",
      href: "/",
    },
    secondary: {
      text: "View Docs",
      href: "#",
    },
  },
};

export const footerConfig = {
  cta: {
    headline: "Start building on Canton today",
    placeholder: "Enter your email",
    button: "Join Waitlist",
  },
  copyright: `© ${new Date().getFullYear()} Ginie DAML by BlockXAI. All rights reserved.`,
};

/**
 * ============================================================================
 * FEATURE FLAGS
 * ============================================================================
 * 
 * Toggle features on/off without touching component code.
 */

export const features = {
  smoothScroll: true,
  testimonialAutoplay: true,
  parallaxHero: true,
  blurInHeadline: true,
};

/**
 * ============================================================================
 * THEME CONFIGURATION
 * ============================================================================
 * 
 * Colors are defined in globals.css using CSS custom properties.
 * This config controls which theme features are enabled.
 */

export const themeConfig = {
  defaultTheme: "system" as "light" | "dark" | "system",
  enableSystemTheme: true,
};
