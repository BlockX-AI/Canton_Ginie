---
name: react-bits-combined
description: >
  Install and integrate components from both React Bits (free, open registry)
  and React Bits Pro (premium, licensed registry) into React/Next.js apps
  using the shadcn registry CLI. Use this skill when the user wants animated
  text effects, cursor animations, interactive UI components, background
  effects, WebGL shaders, GSAP/Framer Motion animations, full page section
  blocks (hero, pricing, navigation, footer, FAQ, CTA, auth, stats, blog,
  contact, features, social proof), or complete landing page templates.
  Trigger on "react bits", "reactbits", "@react-bits", "@reactbits-pro",
  "@reactbits-starter", or any request for premium animated React components.
license: React Bits — MIT open registry. React Bits Pro — Proprietary (license key required).
compatibility: Requires Node.js 18+, React 18/19, Next.js 14+ (App Router recommended). Tailwind CSS v4 recommended.
metadata:
  author: reactbits / reactbits-pro
  version: "2.0"
---

# React Bits + React Bits Pro — Combined Skill

This skill covers two related but distinct libraries:

| Library | Registry prefix | Access | CLI suffix |
|---|---|---|---|
| **React Bits** (free) | `@react-bits` | Public — no license needed | `-TS-TW` |
| **React Bits Pro** (premium) | `@reactbits-starter` / `@reactbits-pro` | Requires paid license key | `-tw` / `-css` (components) or no suffix (blocks) |

---

## Part 1 — React Bits (Free)

React Bits is a free, open shadcn-compatible component registry offering 100+ animated components across four categories: Text Animations, Animations, UI Components, and Background Effects.

### Installing React Bits components

No license key required. Run commands directly:

```bash
npx shadcn@latest add @react-bits/{ComponentSlug}-TS-TW
```

All components use TypeScript + Tailwind CSS (`-TS-TW` suffix).

### Prerequisites

Ensure your project has shadcn set up with a `components.json` and the `cn` utility:

```typescript
// lib/utils.ts
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

If missing: `npm install clsx tailwind-merge`

---

### Category 1 — Text Animations

Animated typographic effects for headings, labels, and body copy.

| Component | CLI Command | Description |
|---|---|---|
| **Split Text** | `npx shadcn@latest add @react-bits/SplitText-TS-TW` | Splits text into characters/words and animates them in with staggered reveals and entrance effects |
| **Blur Text** | `npx shadcn@latest add @react-bits/BlurText-TS-TW` | Blurs each word or character as they animate into focus — smooth entrance effect |
| **Circular Text** | `npx shadcn@latest add @react-bits/CircularText-TS-TW` | Arranges text along a circular SVG path with optional continuous rotation |
| **Text Type** | `npx shadcn@latest add @react-bits/TextType-TS-TW` | Classic typewriter effect that types out strings one character at a time with a blinking cursor |
| **Shuffle** | `npx shadcn@latest add @react-bits/Shuffle-TS-TW` | Shuffles characters randomly before resolving to the final text — scrambled reveal |
| **Shiny Text** | `npx shadcn@latest add @react-bits/ShinyText-TS-TW` | Adds a sweeping metallic shine/gloss animation over text |
| **Text Pressure** | `npx shadcn@latest add @react-bits/TextPressure-TS-TW` | Variable-font weight that responds to mouse proximity — letters swell and compress |
| **Curved Loop** | `npx shadcn@latest add @react-bits/CurvedLoop-TS-TW` | Text that endlessly loops along a curved SVG arc path |
| **Fuzzy Text** | `npx shadcn@latest add @react-bits/FuzzyText-TS-TW` | Applies a fuzzy noise/static distortion to text, sharpening on hover |
| **Gradient Text** | `npx shadcn@latest add @react-bits/GradientText-TS-TW` | Animated moving gradient fill applied to text with configurable colors and speed |
| **Falling Text** | `npx shadcn@latest add @react-bits/FallingText-TS-TW` | Characters fall down with gravity physics — triggered on hover or load |
| **Text Cursor** | `npx shadcn@latest add @react-bits/TextCursor-TS-TW` | A custom cursor that trails text characters or a label as the mouse moves |
| **Decrypted Text** | `npx shadcn@latest add @react-bits/DecryptedText-TS-TW` | Simulates a decryption animation cycling random characters before revealing the real text |
| **True Focus** | `npx shadcn@latest add @react-bits/TrueFocus-TS-TW` | Word-by-word blurred text with a sharp focus spotlight that slides across on hover |
| **Scroll Float** | `npx shadcn@latest add @react-bits/ScrollFloat-TS-TW` | Words float up and settle into position as the section scrolls into the viewport |
| **Scroll Reveal** | `npx shadcn@latest add @react-bits/ScrollReveal-TS-TW` | Lines or words fade/slide in sequentially as the user scrolls down the page |
| **ASCII Text** | `npx shadcn@latest add @react-bits/ASCIIText-TS-TW` | Renders 3D text using ASCII characters as the pixel medium — retro terminal aesthetic |
| **Scrambled Text** | `npx shadcn@latest add @react-bits/ScrambledText-TS-TW` | Randomises characters continuously, gradually resolving to the real string on trigger |
| **Rotating Text** | `npx shadcn@latest add @react-bits/RotatingText-TS-TW` | Cycles through a list of words/phrases with smooth vertical or fade transition |
| **Glitch Text** | `npx shadcn@latest add @react-bits/GlitchText-TS-TW` | Canvas-based sticky glitch effect with RGB channel separation, responding to cursor |
| **Scroll Velocity** | `npx shadcn@latest add @react-bits/ScrollVelocity-TS-TW` | Text speed and distortion scales with scroll velocity — rubber-band inertia feel |
| **Variable Proximity** | `npx shadcn@latest add @react-bits/VariableProximity-TS-TW` | Variable-font axes (weight, width, slant) respond to mouse distance from each letter |
| **Count Up** | `npx shadcn@latest add @react-bits/CountUp-TS-TW` | Animates a number counting up from zero (or any value) with easing and formatting |

---

### Category 2 — Animations

Interactive cursor effects, hover reactions, and visual interaction components.

| Component | CLI Command | Description |
|---|---|---|
| **Animated Content** | `npx shadcn@latest add @react-bits/AnimatedContent-TS-TW` | Wrapper that animates its children in with configurable entrance transitions |
| **Fade Content** | `npx shadcn@latest add @react-bits/FadeContent-TS-TW` | Fades children into view on scroll or mount with direction and delay options |
| **Electric Border** | `npx shadcn@latest add @react-bits/ElectricBorder-TS-TW` | Animated electric/lightning border effect that traces the outline of any element |
| **Orbit Images** | `npx shadcn@latest add @react-bits/OrbitImages-TS-TW` | Images orbit a central element in concentric circular paths with configurable speed |
| **Pixel Transition** | `npx shadcn@latest add @react-bits/PixelTransition-TS-TW` | Page/section transitions using a pixelated dissolve or build-up effect |
| **Glare Hover** | `npx shadcn@latest add @react-bits/GlareHover-TS-TW` | Mouse-following specular glare highlight layered over a card or image |
| **Antigravity** | `npx shadcn@latest add @react-bits/Antigravity-TS-TW` | Elements float and drift away from the cursor as if repelled by an invisible force |
| **Logo Loop** | `npx shadcn@latest add @react-bits/LogoLoop-TS-TW` | Infinite horizontal marquee of logos/images with hover-pause and configurable speed |
| **Target Cursor** | `npx shadcn@latest add @react-bits/TargetCursor-TS-TW` | Replaces the cursor with animated crosshair/target rings that track mouse position |
| **Magic Rings** | `npx shadcn@latest add @react-bits/MagicRings-TS-TW` | Concentric glowing rings that follow the cursor with spring-physics lag |
| **Laser Flow** | `npx shadcn@latest add @react-bits/LaserFlow-TS-TW` | Laser beam lines that emanate from the cursor, flowing across the page |
| **Magnet Lines** | `npx shadcn@latest add @react-bits/MagnetLines-TS-TW` | Grid of short line segments that orient themselves toward the cursor like a magnetic field |
| **Ghost Cursor** | `npx shadcn@latest add @react-bits/GhostCursor-TS-TW` | Trailing ghost/shadow cursors that follow the real cursor with decaying opacity |
| **Gradual Blur** | `npx shadcn@latest add @react-bits/GradualBlur-TS-TW` | Applies a distance-based blur that increases as you move away from the cursor |
| **Click Spark** | `npx shadcn@latest add @react-bits/ClickSpark-TS-TW` | Spark/firework burst particle explosion on every mouse click |
| **Magnet** | `npx shadcn@latest add @react-bits/Magnet-TS-TW` | Element is magnetically attracted to the cursor, snapping/drifting toward it on hover |
| **Sticker Peel** | `npx shadcn@latest add @react-bits/StickerPeel-TS-TW` | Realistic sticker peel corner effect — element curls away on hover revealing the back |
| **Pixel Trail** | `npx shadcn@latest add @react-bits/PixelTrail-TS-TW` | Leaves a fading pixelated trail of blocks as the cursor moves across the screen |
| **Cubes** | `npx shadcn@latest add @react-bits/Cubes-TS-TW` | 3D rotating cube grid that reacts to cursor position with perspective transforms |
| **Metallic Paint** | `npx shadcn@latest add @react-bits/MetallicPaint-TS-TW` | Fluid metallic paint/liquid-metal shader effect that distorts in response to mouse |
| **Noise** | `npx shadcn@latest add @react-bits/Noise-TS-TW` | Animated Perlin/simplex noise overlay — grain texture that shifts over time |
| **Shape Blur** | `npx shadcn@latest add @react-bits/ShapeBlur-TS-TW` | Blurred geometric shapes that drift and morph in the background |
| **Crosshair** | `npx shadcn@latest add @react-bits/Crosshair-TS-TW` | Full-viewport crosshair lines that follow the cursor with configurable style |
| **Image Trail** | `npx shadcn@latest add @react-bits/ImageTrail-TS-TW` | A trail of images appears and fades as the cursor moves, like an image-spray effect |
| **Ribbons** | `npx shadcn@latest add @react-bits/Ribbons-TS-TW` | Flowing 3D ribbon/cloth strips that wave and react to mouse interaction |
| **Splash Cursor** | `npx shadcn@latest add @react-bits/SplashCursor-TS-TW` | Fluid ink-splash simulation that erupts from the cursor on movement |
| **Meta Balls** | `npx shadcn@latest add @react-bits/MetaBalls-TS-TW` | Classic metaball blobs that merge and separate as they drift around the screen |
| **Blob Cursor** | `npx shadcn@latest add @react-bits/BlobCursor-TS-TW` | A fluid blob/goo that trails the cursor with elastic spring physics |
| **Star Border** | `npx shadcn@latest add @react-bits/StarBorder-TS-TW` | Animated star/sparkle particles that orbit the border of a card or button |

---

### Category 3 — UI Components

Interactive UI widgets, galleries, navigation patterns, and layout components.

| Component | CLI Command | Description |
|---|---|---|
| **Animated List** | `npx shadcn@latest add @react-bits/AnimatedList-TS-TW` | List items animate in sequentially with stagger, entrance styles, and exit animations |
| **Scroll Stack** | `npx shadcn@latest add @react-bits/ScrollStack-TS-TW` | Cards or panels stack/peel away as the user scrolls — sticky scroll-driven layering |
| **Bubble Menu** | `npx shadcn@latest add @react-bits/BubbleMenu-TS-TW` | Floating action menu where items expand outward in a bubble/radial pattern on trigger |
| **Magic Bento** | `npx shadcn@latest add @react-bits/MagicBento-TS-TW` | Bento-grid layout with hover-triggered shimmer, glow, and depth effects per cell |
| **Circular Gallery** | `npx shadcn@latest add @react-bits/CircularGallery-TS-TW` | Draggable circular/carousel gallery where images arc around a central focal point |
| **Reflective Card** | `npx shadcn@latest add @react-bits/ReflectiveCard-TS-TW` | Card with real-time dynamic reflection and specular highlight following mouse position |
| **Card Nav** | `npx shadcn@latest add @react-bits/CardNav-TS-TW` | Navigation system where menu items are large hoverable cards with preview content |
| **Stack** | `npx shadcn@latest add @react-bits/Stack-TS-TW` | Draggable, fanned-out card stack — click or drag to cycle through the deck |
| **Fluid Glass** | `npx shadcn@latest add @react-bits/FluidGlass-TS-TW` | Glassmorphism surface with live fluid/ripple distortion inside the blur layer |
| **Pill Nav** | `npx shadcn@latest add @react-bits/PillNav-TS-TW` | Navigation bar with a sliding pill/indicator that animates between active items |
| **Tilted Card** | `npx shadcn@latest add @react-bits/TiltedCard-TS-TW` | 3D perspective card that tilts to follow the cursor with configurable intensity |
| **Masonry** | `npx shadcn@latest add @react-bits/Masonry-TS-TW` | Animated masonry/Pinterest-style grid with staggered entrance and responsive columns |
| **Glass Surface** | `npx shadcn@latest add @react-bits/GlassSurface-TS-TW` | Highly polished glassmorphism panel with configurable blur, tint, border, and glow |
| **Dome Gallery** | `npx shadcn@latest add @react-bits/DomeGallery-TS-TW` | Images displayed on a 3D dome/sphere surface that rotates and responds to drag |
| **Chroma Grid** | `npx shadcn@latest add @react-bits/ChromaGrid-TS-TW` | Grid of cards with chromatic aberration and color-shift effects on hover |
| **Folder** | `npx shadcn@latest add @react-bits/Folder-TS-TW` | Animated file-folder UI element that opens/closes, revealing stacked content inside |
| **Staggered Menu** | `npx shadcn@latest add @react-bits/StaggeredMenu-TS-TW` | Full-screen or overlay menu where items stagger in with dramatic animated entrances |
| **Model Viewer** | `npx shadcn@latest add @react-bits/ModelViewer-TS-TW` | Interactive 3D model viewer with drag-to-rotate, zoom, and lighting controls |
| **Lanyard** | `npx shadcn@latest add @react-bits/Lanyard-TS-TW` | Physics-simulated lanyard/badge that swings, sways, and responds to drag |
| **Profile Card** | `npx shadcn@latest add @react-bits/ProfileCard-TS-TW` | Interactive profile/social card with 3D tilt, avatar glow, and hover reveal details |
| **Dock** | `npx shadcn@latest add @react-bits/Dock-TS-TW` | macOS-style dock with magnification on hover and spring-physics icon scaling |
| **Gooey Nav** | `npx shadcn@latest add @react-bits/GooeyNav-TS-TW` | Navigation with a gooey/fluid blob that stretches between items as you move between them |
| **Pixel Card** | `npx shadcn@latest add @react-bits/PixelCard-TS-TW` | Card with a pixel-art style reveal or hover effect — grid of colored squares |
| **Carousel** | `npx shadcn@latest add @react-bits/Carousel-TS-TW` | Smooth touch/drag carousel with momentum, snap points, and configurable layout |
| **Spotlight Card** | `npx shadcn@latest add @react-bits/SpotlightCard-TS-TW` | Card with a mouse-following radial spotlight/cone light reveal on its surface |
| **Border Glow** | `npx shadcn@latest add @react-bits/BorderGlow-TS-TW` | Animated glowing border that sweeps a light/color highlight around the element's edge |
| **Flying Posters** | `npx shadcn@latest add @react-bits/FlyingPosters-TS-TW` | Posters/images fly through 3D space in a tunnel or scattered formation |
| **Card Swap** | `npx shadcn@latest add @react-bits/CardSwap-TS-TW` | Cards swap positions with fluid animated transitions — sortable/shuffleable layout |
| **Glass Icons** | `npx shadcn@latest add @react-bits/GlassIcons-TS-TW` | Icon set housed in glossy glass capsule/pill buttons with depth and reflection |
| **Decay Card** | `npx shadcn@latest add @react-bits/DecayCard-TS-TW` | Card with a disintegration/decay hover effect — fragments break apart on interaction |
| **Flowing Menu** | `npx shadcn@latest add @react-bits/FlowingMenu-TS-TW` | Navigation menu where a fluid/wave background flows and morphs behind hovered items |
| **Elastic Slider** | `npx shadcn@latest add @react-bits/ElasticSlider-TS-TW` | Range slider with elastic/spring-physics handle that overshoots and bounces back |
| **Counter** | `npx shadcn@latest add @react-bits/Counter-TS-TW` | Mechanical slot-machine style digit counter with rolling number transition |
| **Infinite Menu** | `npx shadcn@latest add @react-bits/InfiniteMenu-TS-TW` | Circular infinite-scroll menu where items loop continuously around a 3D ring |
| **Stepper** | `npx shadcn@latest add @react-bits/Stepper-TS-TW` | Multi-step wizard UI with animated transitions between steps and progress tracking |
| **Bounce Cards** | `npx shadcn@latest add @react-bits/BounceCards-TS-TW` | Stack of cards that spring and bounce into a fanned layout on hover |

---

### Category 4 — Background Effects

Full-bleed animated backgrounds and ambient visual effects for sections and pages.

| Component | CLI Command | Description |
|---|---|---|
| **Liquid Ether** | `npx shadcn@latest add @react-bits/LiquidEther-TS-TW` | Slow-moving iridescent liquid-like shader — oil-on-water colour play |
| **Prism** | `npx shadcn@latest add @react-bits/Prism-TS-TW` | Light refraction through a prism scatters rainbow spectrum bands across the surface |
| **Dark Veil** | `npx shadcn@latest add @react-bits/DarkVeil-TS-TW` | Dark semi-transparent veil/smoke that shifts and swirls over content |
| **Light Pillar** | `npx shadcn@latest add @react-bits/LightPillar-TS-TW` | Vertical columns of glowing light that pulse upward like cathedral rays |
| **Silk** | `npx shadcn@latest add @react-bits/Silk-TS-TW` | Smooth flowing silk-fabric simulation with configurable colors and ripple speed |
| **Floating Lines** | `npx shadcn@latest add @react-bits/FloatingLines-TS-TW` | Thin lines drift slowly upward/sideways in a calm ambient floating animation |
| **Light Rays** | `npx shadcn@latest add @react-bits/LightRays-TS-TW` | God-rays / crepuscular light beams that fan out from a central point |
| **Pixel Blast** | `npx shadcn@latest add @react-bits/PixelBlast-TS-TW` | Pixels scatter and reassemble in an explosive animated mosaic pattern |
| **Color Bends** | `npx shadcn@latest add @react-bits/ColorBends-TS-TW` | Slow morphing color gradient blobs that bend and flow into each other |
| **Evil Eye** | `npx shadcn@latest add @react-bits/EvilEye-TS-TW` | Stylised eye shape that tracks the cursor with iris movement and pupil dilation |
| **Line Waves** | `npx shadcn@latest add @react-bits/LineWaves-TS-TW` | Rows of animated sine-wave lines that undulate at varying speeds and amplitudes |
| **Radar** | `npx shadcn@latest add @react-bits/Radar-TS-TW` | Rotating radar sweep animation with circular grid lines and blip effects |
| **Soft Aurora** | `npx shadcn@latest add @react-bits/SoftAurora-TS-TW` | Gentle pastel aurora borealis curtains that softly drift and shift in color |
| **Aurora** | `npx shadcn@latest add @react-bits/Aurora-TS-TW` | Vivid northern-lights aurora with bold green/purple/cyan bands sweeping the sky |
| **Plasma** | `npx shadcn@latest add @react-bits/Plasma-TS-TW` | Classic plasma effect — psychedelic cycling color blobs from sine-wave math |
| **Particles** | `npx shadcn@latest add @react-bits/Particles-TS-TW` | Configurable floating particle field with connection lines and mouse repulsion/attraction |
| **Gradient Blinds** | `npx shadcn@latest add @react-bits/GradientBlinds-TS-TW` | Venetian-blind panels of gradient color that open and close with scroll or hover |
| **Grainient** | `npx shadcn@latest add @react-bits/Grainient-TS-TW` | Gradient background with an animated film-grain/noise texture overlay |
| **Grid Scan** | `npx shadcn@latest add @react-bits/GridScan-TS-TW` | A scanning line sweeps across a grid/graph-paper background like a radar sweep |
| **Beams** | `npx shadcn@latest add @react-bits/Beams-TS-TW` | Glowing directional beams/rays shoot across the screen in animated bursts |
| **Pixel Snow** | `npx shadcn@latest add @react-bits/PixelSnow-TS-TW` | Pixelated snow particles fall at varying speeds — retro 8-bit snowfall |
| **Lightning** | `npx shadcn@latest add @react-bits/Lightning-TS-TW` | Procedural lightning bolt arcs that fork and flash across the background |
| **Prismatic Burst** | `npx shadcn@latest add @react-bits/PrismaticBurst-TS-TW` | Explosive prismatic rainbow burst emanating outward from a center point |
| **Galaxy** | `npx shadcn@latest add @react-bits/Galaxy-TS-TW` | Spiral galaxy star-field that slowly rotates, with configurable star density and color |
| **Dither** | `npx shadcn@latest add @react-bits/Dither-TS-TW` | Retro ordered dithering pattern applied as an animated gradient/texture overlay |
| **Faulty Terminal** | `npx shadcn@latest add @react-bits/FaultyTerminal-TS-TW` | CRT/terminal scan-lines with glitch artifacts, phosphor glow, and flicker |
| **Ripple Grid** | `npx shadcn@latest add @react-bits/RippleGrid-TS-TW` | Dot/circle grid that ripples outward from cursor click or pointer position |
| **Dot Grid** | `npx shadcn@latest add @react-bits/DotGrid-TS-TW` | Ambient grid of dots that wave, pulse, or scale in response to mouse proximity |
| **Threads** | `npx shadcn@latest add @react-bits/Threads-TS-TW` | Fine thread-like lines weave and drift creating a textile/fiber ambient background |
| **Hyperspeed** | `npx shadcn@latest add @react-bits/Hyperspeed-TS-TW` | Star-warp hyperspace jump — streaking white lines from center like jumping to lightspeed |
| **Iridescence** | `npx shadcn@latest add @react-bits/Iridescence-TS-TW` | Soap-bubble iridescent surface that shifts through the spectrum on mouse movement |
| **Waves** | `npx shadcn@latest add @react-bits/Waves-TS-TW` | Layered SVG/canvas wave animation with configurable amplitude, speed, and fill |
| **Grid Distortion** | `npx shadcn@latest add @react-bits/GridDistortion-TS-TW` | Grid/mesh that warps and bulges around the cursor like a rubber sheet being pushed |
| **Ballpit** | `npx shadcn@latest add @react-bits/Ballpit-TS-TW` | Physics-simulated bouncing balls that collide with walls and each other |
| **Orb** | `npx shadcn@latest add @react-bits/Orb-TS-TW` | Single glowing 3D orb with configurable hue, glow radius, and floating animation |
| **Letter Glitch** | `npx shadcn@latest add @react-bits/LetterGlitch-TS-TW` | Background filled with randomly glitching ASCII/letter characters in a matrix style |
| **Grid Motion** | `npx shadcn@latest add @react-bits/GridMotion-TS-TW` | Grid of tiles that shift, translate, or rotate in coordinated animated motion |
| **Shape Grid** | `npx shadcn@latest add @react-bits/ShapeGrid-TS-TW` | Geometric shapes (circles, triangles, squares) arranged in a grid that animate on scroll/hover |
| **Liquid Chrome** | `npx shadcn@latest add @react-bits/LiquidChrome-TS-TW` | High-gloss liquid chrome/mercury shader that flows and reflects as it animates |
| **Balatro** | `npx shadcn@latest add @react-bits/Balatro-TS-TW` | Inspired by the card game — swirling vortex of rich purples and card-suit motifs |

---

### Usage example — React Bits (free)

```tsx
import SplitText from "@/components/react-bits/split-text";
import Particles from "@/components/react-bits/particles";

export default function HeroSection() {
  return (
    <div className="relative h-screen w-full">
      {/* Ambient background */}
      <Particles className="absolute inset-0" quantity={120} />

      {/* Animated heading */}
      <div className="relative z-10 flex items-center justify-center h-full">
        <SplitText
          text="Build something beautiful."
          className="text-6xl font-bold text-white"
          delay={80}
          animationFrom={{ opacity: 0, transform: "translate3d(0,40px,0)" }}
          animationTo={{ opacity: 1, transform: "translate3d(0,0,0)" }}
        />
      </div>
    </div>
  );
}
```

---

---

## Part 2 — React Bits Pro (Premium)

React Bits Pro is a paid shadcn-compatible registry with 88+ animated UI components and 120+ full page-section blocks. It requires a valid license key.

### Tier overview

| Registry | Content | Tier |
|---|---|---|
| `@reactbits-starter` | 88 animated UI components | Starter / Pro / Ultimate |
| `@reactbits-pro` | 120+ page section blocks | Pro / Ultimate only |

### Component variants (starter registry)

- **`-tw`** — Tailwind CSS via `cn()`. Preferred for Tailwind projects.
- **`-css`** — Co-located `.css` file. Use for non-Tailwind projects.

Blocks (`@reactbits-pro`) are Tailwind-only with no suffix.

---

### Setup — Step 1: License key

Add to `.env.local` (never commit this file):

```
REACTBITS_LICENSE_KEY=your-license-key-here
```

### Setup — Step 2: Configure `components.json`

Merge the `registries` key into your existing `components.json`:

```json
{
  "registries": {
    "@reactbits-starter": {
      "url": "https://pro.reactbits.dev/api/r/starter/{name}.json",
      "headers": {
        "Authorization": "Bearer ${REACTBITS_LICENSE_KEY}"
      }
    },
    "@reactbits-pro": {
      "url": "https://pro.reactbits.dev/api/r/pro/{name}.json",
      "headers": {
        "Authorization": "Bearer ${REACTBITS_LICENSE_KEY}"
      }
    }
  }
}
```

Do **not** overwrite existing `components.json` fields.

---

### React Bits Pro — Components (`@reactbits-starter`)

#### Text & Typography

| Component | CLI Command | Description |
|---|---|---|
| **Staggered Text** | `npx shadcn@latest add @reactbits-starter/staggered-text-tw` | Flexible text animation with multiple staggered reveal presets |
| **Glitch Text** | `npx shadcn@latest add @reactbits-starter/glitch-text-tw` | Canvas-based sticky glitch effect with RGB shift, responding to cursor |
| **Text Path** | `npx shadcn@latest add @reactbits-starter/text-path-tw` | Animated text following a custom SVG path with GSAP |
| **3D Text Reveal** | `npx shadcn@latest add @reactbits-starter/3d-text-reveal-tw` | Scroll-triggered 3D perspective text entrance with GSAP ScrollTrigger |
| **Particle Text** | `npx shadcn@latest add @reactbits-starter/particle-text-tw` | Interactive 3D particle system that forms readable text using Three.js |
| **Text Scatter** | `npx shadcn@latest add @reactbits-starter/text-scatter-tw` | Letters scatter outward from their original positions on hover |
| **3D Letter Swap** | `npx shadcn@latest add @reactbits-starter/3d-letter-swap-tw` | Staggered 3D flip/rotation between characters revealing a new word |
| **Blur Highlight** | `npx shadcn@latest add @reactbits-starter/blur-highlight-tw` | Blur-in reveal with automatic text highlighting using Framer Motion |

#### Cursor Effects

| Component | CLI Command | Description |
|---|---|---|
| **Smooth Cursor** | `npx shadcn@latest add @reactbits-starter/smooth-cursor-tw` | Canvas cursor trail with spring physics — buttery smooth lag and deceleration |
| **Custom Cursor** | `npx shadcn@latest add @reactbits-starter/custom-cursor-tw` | Cursor that morphs shape when hovering over interactive target elements |
| **Dither Cursor** | `npx shadcn@latest add @reactbits-starter/dither-cursor-tw` | Pixelated ordered-dither pattern trails the cursor position |
| **Ascii Cursor** | `npx shadcn@latest add @reactbits-starter/ascii-cursor-tw` | Trail of ASCII characters that fade out behind the cursor |
| **Glass Cursor** | `npx shadcn@latest add @reactbits-starter/glass-cursor-tw` | Metaball glass orb cursor with live refraction and blur — Three.js powered |

#### Cards & Interactive Elements

| Component | CLI Command | Description |
|---|---|---|
| **Shader Card** | `npx shadcn@latest add @reactbits-starter/shader-card-tw` | Card housing a live animated WebGL shader as its background |
| **Chroma Card** | `npx shadcn@latest add @reactbits-starter/chroma-card-tw` | Card with animated chromatic color shift on hover |
| **Credit Card** | `npx shadcn@latest add @reactbits-starter/credit-card-tw` | Interactive 3D credit card with parallax tilt and flip animation |
| **Depth Card** | `npx shadcn@latest add @reactbits-starter/depth-card-tw` | Perspective depth/parallax layers within a card responding to mouse |
| **Modal Cards** | `npx shadcn@latest add @reactbits-starter/modal-cards-tw` | Expandable cards that animate open to full-screen modal overlays |
| **Rotating Cards** | `npx shadcn@latest add @reactbits-starter/rotating-cards-tw` | 3D circular carousel of draggable cards arranged in a ring |
| **Parallax Cards** | `npx shadcn@latest add @reactbits-starter/parallax-cards-tw` | Cards with layered 3D parallax depth responding to mouse movement |
| **Click Stack** | `npx shadcn@latest add @reactbits-starter/click-stack-tw` | GSAP-animated card stack — click to cycle to the next card |
| **Warped Card** | `npx shadcn@latest add @reactbits-starter/warped-card-tw` | Image card with a mouse-following bulge/lens distortion shader (Three.js) |

#### Backgrounds & Visual Effects

| Component | CLI Command | Description |
|---|---|---|
| **Silk Waves** | `npx shadcn@latest add @reactbits-starter/silk-waves-tw` | Smooth flowing silk-fabric wave animation powered by Three.js |
| **Shader Waves** | `npx shadcn@latest add @reactbits-starter/shader-waves-tw` | Wave patterns with noise distortion in a WebGL shader |
| **Chroma Waves** | `npx shadcn@latest add @reactbits-starter/chroma-waves-tw` | Chromatic noise-distortion wave shader with vivid colour output |
| **Aurora Blur** | `npx shadcn@latest add @reactbits-starter/aurora-blur-tw` | Soft ethereal aurora borealis CSS blur animation |
| **Gradient Blob** | `npx shadcn@latest add @reactbits-starter/gradient-blob-tw` | Morphing 3D gradient blob that responds to cursor proximity |
| **AI Blob** | `npx shadcn@latest add @reactbits-starter/ai-blob-tw` | Organic animated 3D blob with glow/pulse — classic "AI orb" aesthetic |
| **Dither Wave** | `npx shadcn@latest add @reactbits-starter/dither-wave-tw` | Sine wave with retro ordered-dithering rendering |
| **Radial Liquid** | `npx shadcn@latest add @reactbits-starter/radial-liquid-tw` | Radial shader with concentric liquid/ripple distortions |
| **Grain Wave** | `npx shadcn@latest add @reactbits-starter/grain-wave-tw` | Animated grainy wave texture — noisy and organic |
| **Glass Flow** | `npx shadcn@latest add @reactbits-starter/glass-flow-tw` | Flowing glass-like blur and light-refraction animation |
| **Falling Rays** | `npx shadcn@latest add @reactbits-starter/falling-rays-tw` | Light rays falling like luminous rain from above |
| **Light Droplets** | `npx shadcn@latest add @reactbits-starter/light-droplets-tw` | Falling streaks of light with glow trails |
| **Lightspeed** | `npx shadcn@latest add @reactbits-starter/lightspeed-tw` | Hyperspace streak effect — white lines shooting from center |
| **Rising Lines** | `npx shadcn@latest add @reactbits-starter/rising-lines-tw` | Ascending lines and particles with a laser beam centerpiece (Three.js) |
| **Liquid Bars** | `npx shadcn@latest add @reactbits-starter/liquid-bars-tw` | Liquid bar animation with smooth wave-like vertical movement |
| **Liquid Lines** | `npx shadcn@latest add @reactbits-starter/liquid-lines-tw` | Flowing organic liquid line animation |
| **Shadow Bars** | `npx shadcn@latest add @reactbits-starter/shadow-bars-tw` | Animated shadow bars with depth — light and dark stripe rhythm |
| **Color Loops** | `npx shadcn@latest add @reactbits-starter/color-loops-tw` | Animated colorful orbital loops spinning in overlapping rings |
| **Mosaic** | `npx shadcn@latest add @reactbits-starter/mosaic-tw` | Mosaic tile effect with animated wave or video background |
| **Flicker** | `npx shadcn@latest add @reactbits-starter/flicker-tw` | Flickering particle grid — like a neon sign struggling to stay on |
| **Vortex** | `npx shadcn@latest add @reactbits-starter/vortex-tw` | Spinning 3D tunnel vortex with particles spiraling inward |
| **Portal** | `npx shadcn@latest add @reactbits-starter/portal-tw` | Circular portal shader with particle ring and inner glow (Three.js) |
| **Perspective Grid** | `npx shadcn@latest add @reactbits-starter/perspective-grid-tw` | Infinite vanishing-point 3D perspective grid — WebGL powered |
| **Glitter Warp** | `npx shadcn@latest add @reactbits-starter/glitter-warp-tw` | Starfield warp tunnel with glittering particle stream |
| **Star Burst** | `npx shadcn@latest add @reactbits-starter/star-burst-tw` | Star explosion burst with radiating particle trails |
| **Rotating Stars** | `npx shadcn@latest add @reactbits-starter/rotating-stars-tw` | Orbiting star particles in animated concentric rings |
| **Dot Shift** | `npx shadcn@latest add @reactbits-starter/dot-shift-tw` | Grid of dots that shift position in wave-like synchronized motion |
| **Synaptic Shift** | `npx shadcn@latest add @reactbits-starter/synaptic-shift-tw` | Neural-network-style animated connection graph |
| **Ascii Waves** | `npx shadcn@latest add @reactbits-starter/ascii-waves-tw` | Wave animation rendered purely with ASCII characters |
| **Squircle Shift** | `npx shadcn@latest add @reactbits-starter/squircle-shift-tw` | Morphing squircle (square-circle hybrid) shape animation |
| **Center Flow** | `npx shadcn@latest add @reactbits-starter/center-flow-tw` | Radial flow animation emanating from a central origin point |
| **Warp Twister** | `npx shadcn@latest add @reactbits-starter/warp-twister-tw` | Twisting warp/tornado distortion effect |
| **Neon Reveal** | `npx shadcn@latest add @reactbits-starter/neon-reveal-tw` | Neon-lit bar sweeps across revealing content with an electric glow |
| **Agentic Ball** | `npx shadcn@latest add @reactbits-starter/agentic-ball-tw` | 3D shader orb with configurable hue, swirl intensity, and complexity (Three.js) |
| **Black Hole** | `npx shadcn@latest add @reactbits-starter/black-hole-tw` | Gravitational particle vortex with hue cycling — lensing/accretion disk visual |
| **Blurred Rays** | `npx shadcn@latest add @reactbits-starter/blurred-rays-tw` | Flickering vertical light beams with a dreamy bloom/blur effect |
| **Flame Paths** | `npx shadcn@latest add @reactbits-starter/flame-paths-tw` | Animated flame-like wave paths rendered with Three.js |
| **Frame Border** | `npx shadcn@latest add @reactbits-starter/frame-border-tw` | Noise-textured animated border that frames content with organic edges |
| **Gradient Bars** | `npx shadcn@latest add @reactbits-starter/gradient-bars-tw` | Animated striped gradient bars shifting in hue and position |
| **Halftone Vortex** | `npx shadcn@latest add @reactbits-starter/halftone-vortex-tw` | Cursor-reactive halftone dot grid swirling into a vortex pattern |
| **Halftone Wave** | `npx shadcn@latest add @reactbits-starter/halftone-wave-tw` | Animated halftone dot grid undulating with noise displacement |
| **Liquid Ascii** | `npx shadcn@latest add @reactbits-starter/liquid-ascii-tw` | Fluid simulation rendered entirely as ASCII characters |
| **Metallic Swirl** | `npx shadcn@latest add @reactbits-starter/metallic-swirl-tw` | Metallic swirl shader — brushed chrome in liquid motion |
| **Retro Lines** | `npx shadcn@latest add @reactbits-starter/retro-lines-tw` | Retro perspective grid with neon scrolling wave lines |
| **Rubber Fluid** | `npx shadcn@latest add @reactbits-starter/rubber-fluid-tw` | Rubbery fluid distortion shader — content warps like stretched latex |
| **Simple Swirl** | `npx shadcn@latest add @reactbits-starter/simple-swirl-tw` | Rotating concentric swirl with soft glow effect |
| **Square Matrix** | `npx shadcn@latest add @reactbits-starter/square-matrix-tw` | Animated dot matrix grid with wave and ripple preset animations |
| **Star Swipe** | `npx shadcn@latest add @reactbits-starter/star-swipe-tw` | Conformal star warp shader with a dramatic sweeping motion |
| **Swirl Blend** | `npx shadcn@latest add @reactbits-starter/swirl-blend-tw` | Colorful iterative swirl shader with full palette control |
| **Text Cube** | `npx shadcn@latest add @reactbits-starter/text-cube-tw` | Cursor-following 3D cube with text on each face, depth fade on edges |
| **Watercolor** | `npx shadcn@latest add @reactbits-starter/watercolor-tw` | Animated watercolor noise shader — two colors blending like wet paint |

#### Galleries, Carousels & Layout

| Component | CLI Command | Description |
|---|---|---|
| **Circle Gallery** | `npx shadcn@latest add @reactbits-starter/circle-gallery-tw` | Draggable circular image carousel with momentum and inertia |
| **Gradient Carousel** | `npx shadcn@latest add @reactbits-starter/gradient-carousel-tw` | 3D card carousel with dynamic gradient color extracted from each image |
| **Circles** | `npx shadcn@latest add @reactbits-starter/circles-tw` | Images arranged on rotating orbital rings with configurable radii |
| **Draggable Grid** | `npx shadcn@latest add @reactbits-starter/draggable-grid-tw` | Pannable infinite grid with drag momentum |
| **Animated List** | `npx shadcn@latest add @reactbits-starter/animated-list-tw` | List with multiple configurable entrance animation styles |
| **Comparison Slider** | `npx shadcn@latest add @reactbits-starter/comparison-slider-tw` | Before/after image comparison with a draggable divider |
| **Hover Preview** | `npx shadcn@latest add @reactbits-starter/hover-preview-tw` | Link text reveals an image preview card on hover |
| **Infinite Gallery** | `npx shadcn@latest add @reactbits-starter/infinite-gallery-tw` | 3D infinite scrolling image gallery with drag and mouse-parallax |

#### Miscellaneous

| Component | CLI Command | Description |
|---|---|---|
| **Globe** | `npx shadcn@latest add @reactbits-starter/globe-tw` | Interactive 3D globe with animated arc connections between points |
| **Device** | `npx shadcn@latest add @reactbits-starter/device-tw` | CSS device mockup (phone, browser) that renders custom slot content |
| **Simple Graph** | `npx shadcn@latest add @reactbits-starter/simple-graph-tw` | Animated line graph with hover tooltips and smooth draw-in animation |
| **Preloader** | `npx shadcn@latest add @reactbits-starter/preloader-tw` | Animated loading screen with multiple style presets (Framer Motion) |
| **Shader Reveal** | `npx shadcn@latest add @reactbits-starter/shader-reveal-tw` | Interactive liquid ink/paint reveal effect over images |
| **Liquid Swap** | `npx shadcn@latest add @reactbits-starter/liquid-swap-tw` | Image transition using a liquid glass ball morphing between two images |
| **Pixelate Hover** | `npx shadcn@latest add @reactbits-starter/pixelate-hover-tw` | Image pixelates on hover and sharpens where the cursor reveals it |

---

### React Bits Pro — Page Section Blocks (`@reactbits-pro`)

**Requires Pro or Ultimate license.** Blocks are Tailwind-only and always ask the user which variant number they want (e.g. `hero-1` vs `hero-5`) before installing.

| Category | Slug pattern | Count | Description |
|---|---|---|---|
| **Hero** | `hero-1` … `hero-13` | 13 | Landing heroes — layouts, WebGL, video, carousels |
| **Navigation** | `navigation-1` … `navigation-8` | 8 | Top, side, bottom nav; mobile menus |
| **Features** | `features-1` … `features-5` | 5 | Feature grids, tabs, marquees, carousels |
| **Social Proof** | `social-proof-1` … `social-proof-9` | 9 | Logo grids, testimonials, video players |
| **Pricing** | `pricing-1` … `pricing-6` | 6 | Pricing tables with toggles and comparisons |
| **Stats** | `stats-1` … `stats-8` | 8 | Metrics with charts, maps, count-up animations |
| **FAQ** | `faq-1` … `faq-3` | 3 | Accordion, chat-style, tabbed FAQs |
| **Call To Action** | `cta-1` … `cta-5` | 5 | CTAs with parallax, cursor trails, video masks |
| **Contact** | `contact-1` … `contact-5` | 5 | Contact forms, card layouts, image carousels |
| **Footer** | `footer-1` … `footer-6` | 6 | Footer variants with links, newsletter, branding |
| **Auth** | `auth-1` … `auth-3` | 3 | Sign-in / sign-up form layouts |
| **Blog** | `blog-1` … `blog-5` | 5 | Blog listings and article pages |
| **About** | `about-1` … `about-5` | 5 | Company story, timeline, metrics sections |
| **Showcase** | `showcase-1` … `showcase-3` | 3 | Portfolio and product display sections |
| **How It Works** | `how-it-works-1` … `how-it-works-3` | 3 | Step-by-step process sections |
| **Waitlist** | `waitlist-1` … `waitlist-3` | 3 | Pre-launch email capture sections |
| **Download** | `download-1` … `download-3` | 3 | App / product download sections |
| **Profile** | `profile-1` … `profile-3` | 3 | User profile cards and sections |
| **Comparison** | `comparison-1` … `comparison-3` | 3 | Feature comparison tables and bar charts |
| **404** | `404-1`, `404-2` | 2 | Creative not-found error pages |

**Install a block:**
```bash
npx shadcn@latest add @reactbits-pro/hero-3
npx shadcn@latest add @reactbits-pro/pricing-2
```

**Import pattern** — blocks use named PascalCase exports:
```tsx
// hero-1 → Hero1,  pricing-3 → Pricing3,  navigation-2 → Navigation2
import { Hero1 } from "@/components/blocks/hero-1";
import { Pricing3 } from "@/components/blocks/pricing-3";
```

---

## Key differences at a glance

| | React Bits (free) | React Bits Pro |
|---|---|---|
| Registry | `@react-bits` | `@reactbits-starter` / `@reactbits-pro` |
| License | Free, public | Paid license key required |
| CLI suffix | `-TS-TW` | `-tw` / `-css` (components), none (blocks) |
| Install path | `components/react-bits/` | `components/react-bits/` or `components/blocks/` |
| Import style | Default export | Default (components) / Named (blocks) |
| `"use client"` | Yes — all components | Yes — all components and blocks |

---

## Common dependencies

| Dependency | Used by |
|---|---|
| `three` | All WebGL/shader/3D components |
| `@react-three/fiber` | Some Pro 3D components |
| `@react-three/drei` | Some Pro 3D components |
| `motion` / `framer-motion` | Most animated components, all Pro blocks |
| `gsap` + `@gsap/react` | Text Path, 3D Text Reveal, some blocks |
| `lucide-react` | Most Pro blocks |
| `next-themes` | Dark-mode components |

---

## Troubleshooting

| Error | Fix |
|---|---|
| `Unknown registry @reactbits-starter` | Missing `registries` in `components.json` — add per setup step 2 |
| `Unauthorized` (Pro) | `REACTBITS_LICENSE_KEY` not set in `.env.local` |
| `Forbidden - Insufficient tier` | Pro/Ultimate license required for `@reactbits-pro` blocks |
| Component not found (Pro) | Add `-tw` or `-css` suffix to component slugs; blocks take no suffix |
| WebGL shows blank | Container needs explicit dimensions; ensure `three` is installed |
| GSAP scroll broken | Needs default document scroll; `ScrollTrigger` is auto-registered |
| Blocks unstyled | Ensure Tailwind v4 is configured with `@import "tailwindcss"` in `globals.css` |
| Missing `cn` | `npm install clsx tailwind-merge` then create `lib/utils.ts` |

---

## Best practices

1. **All components are `"use client"`** — never remove this directive; Next.js handles the server/client boundary automatically.
2. **Give WebGL components explicit dimensions** — wrap in a container with defined `width`/`height`.
3. **Lazy-load heavy Three.js components** if not above the fold:
   ```tsx
   import dynamic from "next/dynamic";
   const SilkWaves = dynamic(() => import("@/components/react-bits/silk-waves"), { ssr: false });
   ```
4. **License keys stay in `.env.local`** — never hardcode or commit them.
5. **Tailwind variant always preferred** (`-tw` / `-TS-TW`) when the project uses Tailwind CSS.
6. **Ask for block variant number** before installing Pro blocks — always confirm which variant (e.g. `hero-1` vs `hero-7`) the user wants.
7. **Blocks are starting points** — edit installed `.tsx` files to replace placeholder copy, images, links, colors, and wire up real logic.
