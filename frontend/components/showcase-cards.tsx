"use client";

import { useRef, useEffect, useCallback, useState, useSyncExternalStore, type ReactNode } from "react";
import { motion } from "motion/react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import NextImage from "next/image";

function getIsSafari(): boolean {
  if (typeof window === "undefined") return false;
  const ua = navigator.userAgent.toLowerCase();
  return ua.includes("safari") && !ua.includes("chrome") && !ua.includes("chromium");
}

const emptySubscribe = () => () => {};

function useIsSafari(): boolean {
  return useSyncExternalStore(
    emptySubscribe,
    getIsSafari,
    () => false
  );
}

interface CardData {
  title: string;
  image: string;
}

const cards: CardData[] = [
  {
    title: "Startup Launch Kit",
    image: "/img/mock1_compressed.webp",
  },
  {
    title: "E-commerce Suite",
    image: "/img/mock5_compressed.webp",
  },
  {
    title: "SaaS Dashboard",
    image: "/img/mock9_compressed.webp",
  },
];

const VERTEX_SHADER = `
  attribute vec2 position;
  attribute vec2 uv;
  varying vec2 vUv;
  uniform vec2 uResolution;
  uniform vec2 uTextureResolution;

  vec2 resizeUvCover(vec2 uv, vec2 size, vec2 resolution) {
    vec2 ratio = vec2(
      min((resolution.x / resolution.y) / (size.x / size.y), 1.0),
      min((resolution.y / resolution.x) / (size.y / size.x), 1.0)
    );
    return vec2(
      uv.x * ratio.x + (1.0 - ratio.x) * 0.5,
      uv.y * ratio.y + (1.0 - ratio.y) * 0.5
    );
  }

  void main() {
    vec2 flippedUv = vec2(uv.x, 1.0 - uv.y);
    vUv = resizeUvCover(flippedUv, uTextureResolution, uResolution);
    gl_Position = vec4(position, 0.0, 1.0);
  }
`;

const FRAGMENT_SHADER = `
  precision highp float;
  
  uniform sampler2D uTexture;
  uniform vec2 uMouse;
  uniform float uBulge;
  uniform float uRadius;
  uniform float uStrength;
  
  varying vec2 vUv;

  vec2 bulge(vec2 uv, vec2 center) {
    vec2 delta = uv - center;
    float dist = length(delta);
    
    // Gaussian falloff for smooth organic blend
    float falloff = exp(-dist * dist / (uRadius * uRadius));
    
    // Reduce effect near edges to prevent artifacts
    float edgeFade = smoothstep(0.0, 0.15, uv.x) * smoothstep(0.0, 0.15, 1.0 - uv.x) *
                     smoothstep(0.0, 0.15, uv.y) * smoothstep(0.0, 0.15, 1.0 - uv.y);
    
    // Push pixels outward from center
    float bulgeAmount = falloff * uStrength * uBulge * edgeFade;
    
    vec2 displaced = uv + delta * bulgeAmount;
    
    // Clamp to prevent sampling outside texture
    return clamp(displaced, 0.001, 0.999);
  }

  void main() {
    vec2 bulgeUV = bulge(vUv, uMouse);
    vec4 tex = texture2D(uTexture, bulgeUV);
    gl_FragColor = vec4(tex.rgb, 1.0);
  }
`;

function createShader(
  gl: WebGLRenderingContext,
  type: number,
  source: string
): WebGLShader | null {
  const shader = gl.createShader(type);
  if (!shader) return null;
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    console.error("Shader compile error:", gl.getShaderInfoLog(shader));
    gl.deleteShader(shader);
    return null;
  }
  return shader;
}

function createProgram(
  gl: WebGLRenderingContext,
  vertexShader: WebGLShader,
  fragmentShader: WebGLShader
): WebGLProgram | null {
  const program = gl.createProgram();
  if (!program) return null;
  gl.attachShader(program, vertexShader);
  gl.attachShader(program, fragmentShader);
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    console.error("Program link error:", gl.getProgramInfoLog(program));
    gl.deleteProgram(program);
    return null;
  }
  return program;
}

interface BulgeCardProps {
  title: string;
  imageSrc: string;
  index: number;
}

// Safari-friendly card with CSS hover effect instead of WebGL
function SafariCard({ title, imageSrc, index }: BulgeCardProps): ReactNode {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <motion.div
      className="relative border border-border/25 aspect-4/5 w-full overflow-hidden rounded-xl cursor-pointer"
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, delay: index * 0.1 }}
      viewport={{ once: true }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <motion.div 
        className="absolute inset-0"
        animate={{ scale: isHovered ? 1.1 : 1 }}
        transition={{ duration: 0.5, ease: "easeOut" }}
      >
        <NextImage
          src={imageSrc}
          alt={title}
          fill
          className="object-cover"
          sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
        />
      </motion.div>
      <div
        className="pointer-events-none absolute inset-0 mix-blend-color"
        style={{
          background: "linear-gradient(135deg, #333DA7 0%, #7388DF 100%)",
        }}
        aria-hidden="true"
      />
      <motion.div 
        className="absolute inset-0"
        animate={{ backgroundColor: isHovered ? "rgba(0,0,0,0.1)" : "rgba(0,0,0,0.2)" }}
        transition={{ duration: 0.3 }}
      />
      <div className="absolute inset-0 flex items-center justify-center">
        <h3 className="text-2xl font-medium tracking-tight text-white md:text-3xl">
          {title}
        </h3>
      </div>
    </motion.div>
  );
}

function BulgeCard({ title, imageSrc, index }: BulgeCardProps): ReactNode {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const glRef = useRef<WebGLRenderingContext | null>(null);
  const programRef = useRef<WebGLProgram | null>(null);
  const textureRef = useRef<WebGLTexture | null>(null);
  const rafRef = useRef<number>(0);
  const uniformsRef = useRef<Record<string, WebGLUniformLocation | null>>({});
  const imageLoadedRef = useRef(false);
  const imageSizeRef = useRef({ width: 1, height: 1 });
  const isDisposedRef = useRef(false);

  const mouseX = useRef(0.5);
  const mouseY = useRef(0.5);
  const targetMouseX = useRef(0.5);
  const targetMouseY = useRef(0.5);
  const bulgeValue = useRef(0);
  const targetBulge = useRef(0);

  useEffect(() => {
    isDisposedRef.current = false;
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const gl = canvas.getContext("webgl", {
      antialias: true,
      alpha: false,
    });
    if (!gl) return;
    glRef.current = gl;

    const vertexShader = createShader(gl, gl.VERTEX_SHADER, VERTEX_SHADER);
    const fragmentShader = createShader(gl, gl.FRAGMENT_SHADER, FRAGMENT_SHADER);
    if (!vertexShader || !fragmentShader) return;

    const program = createProgram(gl, vertexShader, fragmentShader);
    if (!program) return;
    programRef.current = program;

    gl.useProgram(program);

    const positions = new Float32Array([
      -1, -1, 0, 0,
       3, -1, 2, 0,
      -1,  3, 0, 2,
    ]);

    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, positions, gl.STATIC_DRAW);

    const positionLoc = gl.getAttribLocation(program, "position");
    const uvLoc = gl.getAttribLocation(program, "uv");

    gl.enableVertexAttribArray(positionLoc);
    gl.vertexAttribPointer(positionLoc, 2, gl.FLOAT, false, 16, 0);
    gl.enableVertexAttribArray(uvLoc);
    gl.vertexAttribPointer(uvLoc, 2, gl.FLOAT, false, 16, 8);

    uniformsRef.current = {
      uTexture: gl.getUniformLocation(program, "uTexture"),
      uMouse: gl.getUniformLocation(program, "uMouse"),
      uBulge: gl.getUniformLocation(program, "uBulge"),
      uRadius: gl.getUniformLocation(program, "uRadius"),
      uStrength: gl.getUniformLocation(program, "uStrength"),
      uResolution: gl.getUniformLocation(program, "uResolution"),
      uTextureResolution: gl.getUniformLocation(program, "uTextureResolution"),
    };

    const uniforms = uniformsRef.current;
    if (uniforms.uRadius) gl.uniform1f(uniforms.uRadius, 0.5);
    if (uniforms.uStrength) gl.uniform1f(uniforms.uStrength, 0.5);

    const texture = gl.createTexture();
    textureRef.current = texture;
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);

    gl.texImage2D(
      gl.TEXTURE_2D,
      0,
      gl.RGBA,
      1,
      1,
      0,
      gl.RGBA,
      gl.UNSIGNED_BYTE,
      new Uint8Array([128, 128, 128, 255])
    );

    const image = new Image();
    image.crossOrigin = "anonymous";
    image.onload = () => {
      if (!gl || !texture || isDisposedRef.current) return;
      imageSizeRef.current = { width: image.width, height: image.height };
      gl.bindTexture(gl.TEXTURE_2D, texture);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, image);
      imageLoadedRef.current = true;
      const texResLoc = uniformsRef.current.uTextureResolution;
      if (texResLoc) {
        gl.uniform2f(texResLoc, image.width, image.height);
      }
    };
    image.src = imageSrc;

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio, 2);
      const width = container.offsetWidth;
      const height = container.offsetHeight;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      gl.viewport(0, 0, canvas.width, canvas.height);
      const resLoc = uniformsRef.current.uResolution;
      if (resLoc) gl.uniform2f(resLoc, width, height);
    };

    resize();
    window.addEventListener("resize", resize);

    const render = () => {
      if (isDisposedRef.current) return;
      
      if (!gl || !programRef.current || !imageLoadedRef.current) {
        rafRef.current = requestAnimationFrame(render);
        return;
      }

      mouseX.current += (targetMouseX.current - mouseX.current) * 0.08;
      mouseY.current += (targetMouseY.current - mouseY.current) * 0.08;
      bulgeValue.current += (targetBulge.current - bulgeValue.current) * 0.06;

      const u = uniformsRef.current;
      if (u.uMouse) gl.uniform2f(u.uMouse, mouseX.current, mouseY.current);
      if (u.uBulge) gl.uniform1f(u.uBulge, bulgeValue.current);

      gl.drawArrays(gl.TRIANGLES, 0, 3);
      rafRef.current = requestAnimationFrame(render);
    };

    render();

    return () => {
      isDisposedRef.current = true;
      cancelAnimationFrame(rafRef.current);
      window.removeEventListener("resize", resize);
      if (program) gl.deleteProgram(program);
      if (texture) gl.deleteTexture(texture);
      glRef.current = null;
      programRef.current = null;
      textureRef.current = null;
    };
  }, [imageSrc]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    targetMouseX.current = (e.clientX - rect.left) / rect.width;
    targetMouseY.current = (e.clientY - rect.top) / rect.height;
  }, []);

  const handleMouseEnter = useCallback(() => {
    targetBulge.current = 1;
  }, []);

  const handleMouseLeave = useCallback(() => {
    targetBulge.current = 0;
  }, []);

  return (
    <motion.div
      ref={containerRef}
      className="group relative border border-border/25 aspect-4/5 w-full overflow-hidden rounded-xl cursor-pointer"
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, delay: index * 0.1 }}
      viewport={{ once: true }}
    >
      <canvas
        ref={canvasRef}
        className="absolute inset-0 h-full w-full"
        aria-hidden="true"
      />
      <div
        className="pointer-events-none absolute inset-0 mix-blend-color"
        style={{
          background: "linear-gradient(135deg, #333DA7 0%, #7388DF 100%)",
        }}
        aria-hidden="true"
      />
      <div className="absolute inset-0 bg-black/20" />
      <div className="absolute inset-0 flex items-center justify-center">
        <h3 className="text-2xl font-medium tracking-tight text-white md:text-3xl">
          {title}
        </h3>
      </div>
    </motion.div>
  );
}

export function ShowcaseCards(): ReactNode {
  const isSafari = useIsSafari();
  const CardComponent = isSafari ? SafariCard : BulgeCard;

  return (
    <section className="px-4 py-20 sm:px-6 md:py-28 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <h2 className="mb-12 text-2xl font-medium tracking-tight text-foreground md:text-3xl lg:text-4xl">
          Pre-built designs, ready to customize
        </h2>

        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {cards.map((card, index) => (
            <CardComponent
              key={card.title}
              title={card.title}
              imageSrc={card.image}
              index={index}
            />
          ))}
        </div>

        <div className="mt-12 flex flex-col gap-2 sm:flex-row items-start sm:justify-between">
          <p className="max-w-md text-lg text-muted-foreground">
            Skip the blank canvas. Start with curated presets crafted for
            specific industries and use cases.
          </p>
          <Link
            href="#"
            className="group flex shrink-0 items-center leading-0 gap-2 text-xl font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            See all
            <ArrowRight className="h-5 w-5 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </div>
      </div>
    </section>
  );
}
