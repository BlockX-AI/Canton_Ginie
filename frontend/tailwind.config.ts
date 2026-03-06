import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        canton: {
          50:  "#f0f4ff",
          100: "#e0e9ff",
          200: "#c7d6ff",
          300: "#a5b8ff",
          400: "#7d8fff",
          500: "#5a6bff",
          600: "#3d4df5",
          700: "#2d38d9",
          800: "#2530af",
          900: "#252e89",
          950: "#161a50",
        },
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "fade-in":    "fadeIn 0.3s ease-in-out",
        "slide-up":   "slideUp 0.4s ease-out",
      },
      keyframes: {
        fadeIn: {
          "0%":   { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%":   { transform: "translateY(20px)", opacity: "0" },
          "100%": { transform: "translateY(0)",    opacity: "1" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
