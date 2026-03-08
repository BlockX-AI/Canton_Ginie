# AI SaaS Landing Page Template

A premium Next.js 16+ landing page template designed for AI products and SaaS applications. Features stunning WebGL effects, smooth animations, and a conversion-focused layout.

## Features

- ✅ **Next.js 16+** with App Router
- ✅ **TypeScript** (strict mode with noUncheckedIndexedAccess)
- ✅ **Tailwind CSS v4** with custom design tokens
- ✅ **Dark Mode** via next-themes with smooth transitions
- ✅ **WebGL Effects** - Fluid cursor, image bulge effects
- ✅ **Motion** via motion/react with reduced-motion support
- ✅ **GSAP Animations** - Scroll-triggered image reveal gallery
- ✅ **SEO Ready** - metadata, Open Graph, Twitter cards
- ✅ **Accessibility** - skip links, focus rings, ARIA labels
- ✅ **Edge Compatible** - no Node-only APIs

## Getting Started

### Install dependencies

```bash
npm install
```

### Run development server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start development server |
| `npm run build` | Build for production |
| `npm run start` | Start production server |
| `npm run lint` | Run ESLint |
| `npm run lint:fix` | Fix ESLint errors |
| `npm run format` | Format code with Prettier |
| `npm run format:check` | Check code formatting |
| `npm run typecheck` | Run TypeScript type checking |

## Project Structure

```
├── app/
│   ├── globals.css        # Design tokens & base styles
│   ├── layout.tsx         # Root layout with providers
│   ├── page.tsx           # Landing page
│   ├── robots.ts          # Dynamic robots.txt
│   ├── sitemap.ts         # Dynamic sitemap
│   └── icon.svg           # Favicon
├── components/
│   ├── bottom-cta.tsx     # Bottom call-to-action section
│   ├── faq.tsx            # FAQ accordion section
│   ├── fluid-cursor.tsx   # WebGL fluid cursor effect
│   ├── footer.tsx         # Site footer with links
│   ├── header.tsx         # Navigation header
│   ├── hero.tsx           # Hero section with prompt UI
│   ├── image-reveal.tsx   # GSAP scroll-triggered gallery
│   ├── pricing.tsx        # Pricing cards section
│   ├── providers.tsx      # Theme & motion providers
│   ├── showcase-cards.tsx # WebGL bulge effect cards
│   ├── skip-to-content.tsx # Skip link for a11y
│   ├── smooth-scroll.tsx  # Lenis smooth scrolling
│   ├── stats.tsx          # Animated statistics bars
│   ├── testimonials.tsx   # Testimonials carousel
│   ├── text-reveal.tsx    # Scroll-triggered text animation
│   ├── theme-switch.tsx   # Floating theme toggle
│   ├── theme-toggle.tsx   # Button theme toggle
│   ├── tools-carousel.tsx # Draggable cards carousel
│   └── trusted-by.tsx     # Logo loop section
├── lib/
│   ├── metadata.ts        # SEO metadata utilities
│   └── motion.tsx         # Motion components & hooks
└── public/
    ├── img/               # Image assets
    ├── svg/               # SVG assets
    └── site.webmanifest   # PWA manifest
```

## Customization

### 1. Update Site Configuration

Edit `lib/metadata.ts` to update:
- Site name, description, and URL
- Social media handles
- Keywords and authors

### 2. Replace Icons

Replace the following files with your brand assets:
- `app/icon.svg` - Favicon (32x32)
- `app/apple-icon.svg` - Apple touch icon (180x180)
- `public/og-image.png` - Open Graph image (1200x630)
- `public/icon-192.png` - PWA icon (192x192)
- `public/icon-512.png` - PWA icon (512x512)

### 3. Customize Design Tokens

Edit `app/globals.css` to modify:
- Color palette (primary, neutral, semantic colors)
- Spacing scale
- Border radii
- Shadows and gradients
- Typography

### 4. Add Routes

Create new routes in the `app/` directory:

```tsx
// app/about/page.tsx
import { createMetadata } from "@/lib/metadata";
import type { Metadata } from "next";

export const metadata: Metadata = createMetadata({
  title: "About Us",
  description: "Learn more about our company.",
  path: "/about",
});

export default function AboutPage() {
  return <main id="main-content">...</main>;
}
```

## Design Tokens

The template uses CSS custom properties for theming. Key tokens:

### Colors
- `--background` / `--foreground` - Page background and text
- `--muted` / `--muted-foreground` - Subtle backgrounds and text
- `--accent` / `--accent-foreground` - Primary action colors
- `--border` / `--ring` - Borders and focus rings

### Shadows
- `--shadow-sm` through `--shadow-2xl` - Elevation levels

### Gradients
- `--gradient-primary` - Brand gradient
- `--gradient-subtle` - Section backgrounds
- `--gradient-radial` - Hero backgrounds

## Accessibility

The template includes:
- Skip-to-content link
- Visible focus rings (keyboard navigation)
- ARIA labels on interactive elements
- Reduced motion support
- Proper heading hierarchy
- WCAG 2.1 AA contrast compliance

## Edge Runtime

All code is Edge-compatible. No Node.js-only APIs are used in runtime code. The template can be deployed to:
- Vercel Edge Functions
- Cloudflare Workers
- Any edge-capable platform

## License

This template is licensed for use in commercial projects. You may not resell or redistribute the template itself.

---

Built with ❤️ using Next.js, Tailwind CSS, and Motion
