"use client";

import { useEffect, useRef, type ReactNode } from "react";

type Uniforms = Record<string, WebGLUniformLocation | null>;

interface FluidCursorProps {
  color?: { r: number; g: number; b: number };
  className?: string;
}

const SHADERS = {
  vertex: `
    precision highp float;
    varying vec2 vUv;
    attribute vec2 a_position;
    varying vec2 vL;
    varying vec2 vR;
    varying vec2 vT;
    varying vec2 vB;
    uniform vec2 u_texel;

    void main () {
      vUv = .5 * (a_position + 1.);
      vL = vUv - vec2(u_texel.x, 0.);
      vR = vUv + vec2(u_texel.x, 0.);
      vT = vUv + vec2(0., u_texel.y);
      vB = vUv - vec2(0., u_texel.y);
      gl_Position = vec4(a_position, 0., 1.);
    }
  `,

  advection: `
    precision highp float;
    precision highp sampler2D;
    varying vec2 vUv;
    uniform sampler2D u_velocity_texture;
    uniform sampler2D u_input_texture;
    uniform vec2 u_texel;
    uniform float u_dt;

    vec4 bilerp (sampler2D sam, vec2 uv, vec2 tsize) {
      vec2 st = uv / tsize - 0.5;
      vec2 iuv = floor(st);
      vec2 fuv = fract(st);
      vec4 a = texture2D(sam, (iuv + vec2(0.5, 0.5)) * tsize);
      vec4 b = texture2D(sam, (iuv + vec2(1.5, 0.5)) * tsize);
      vec4 c = texture2D(sam, (iuv + vec2(0.5, 1.5)) * tsize);
      vec4 d = texture2D(sam, (iuv + vec2(1.5, 1.5)) * tsize);
      return mix(mix(a, b, fuv.x), mix(c, d, fuv.x), fuv.y);
    }

    void main () {
      vec2 coord = vUv - u_dt * bilerp(u_velocity_texture, vUv, u_texel).xy * u_texel;
      float dissipation = .96;
      gl_FragColor = dissipation * bilerp(u_input_texture, coord, u_texel);
      gl_FragColor.a = 1.;
    }
  `,

  divergence: `
    precision highp float;
    precision highp sampler2D;
    varying highp vec2 vUv;
    varying highp vec2 vL;
    varying highp vec2 vR;
    varying highp vec2 vT;
    varying highp vec2 vB;
    uniform sampler2D u_velocity_texture;

    void main () {
      float L = texture2D(u_velocity_texture, vL).x;
      float R = texture2D(u_velocity_texture, vR).x;
      float T = texture2D(u_velocity_texture, vT).y;
      float B = texture2D(u_velocity_texture, vB).y;
      float div = .6 * (R - L + T - B);
      gl_FragColor = vec4(div, 0., 0., 1.);
    }
  `,

  pressure: `
    precision highp float;
    precision highp sampler2D;
    varying highp vec2 vUv;
    varying highp vec2 vL;
    varying highp vec2 vR;
    varying highp vec2 vT;
    varying highp vec2 vB;
    uniform sampler2D u_pressure_texture;
    uniform sampler2D u_divergence_texture;

    void main () {
      float L = texture2D(u_pressure_texture, vL).x;
      float R = texture2D(u_pressure_texture, vR).x;
      float T = texture2D(u_pressure_texture, vT).x;
      float B = texture2D(u_pressure_texture, vB).x;
      float divergence = texture2D(u_divergence_texture, vUv).x;
      float pressure = (L + R + B + T - divergence) * 0.25;
      gl_FragColor = vec4(pressure, 0., 0., 1.);
    }
  `,

  gradientSubtract: `
    precision highp float;
    precision highp sampler2D;
    varying highp vec2 vUv;
    varying highp vec2 vL;
    varying highp vec2 vR;
    varying highp vec2 vT;
    varying highp vec2 vB;
    uniform sampler2D u_pressure_texture;
    uniform sampler2D u_velocity_texture;

    void main () {
      float L = texture2D(u_pressure_texture, vL).x;
      float R = texture2D(u_pressure_texture, vR).x;
      float T = texture2D(u_pressure_texture, vT).x;
      float B = texture2D(u_pressure_texture, vB).x;
      vec2 velocity = texture2D(u_velocity_texture, vUv).xy;
      velocity.xy -= vec2(R - L, T - B);
      gl_FragColor = vec4(velocity, 0., 1.);
    }
  `,

  splat: `
    precision highp float;
    precision highp sampler2D;
    varying vec2 vUv;
    uniform sampler2D u_input_texture;
    uniform float u_ratio;
    uniform vec3 u_point_value;
    uniform vec2 u_point;
    uniform float u_point_size;

    void main () {
      vec2 p = vUv - u_point.xy;
      p.x *= u_ratio;
      vec3 splat = pow(2., -dot(p, p) / u_point_size) * u_point_value;
      vec3 base = texture2D(u_input_texture, vUv).xyz;
      gl_FragColor = vec4(base + splat, 1.);
    }
  `,

  output: `
    precision highp float;
    precision highp sampler2D;
    varying vec2 vUv;
    uniform sampler2D u_output_texture;

    void main () {
      vec3 C = texture2D(u_output_texture, vUv).rgb;
      gl_FragColor = vec4(vec3(1.) - C, 1.);
    }
  `,
};

interface FBO {
  fbo: WebGLFramebuffer;
  width: number;
  height: number;
  attach: (id: number) => number;
}

interface DoubleFBO {
  width: number;
  height: number;
  texelSizeX: number;
  texelSizeY: number;
  read: () => FBO;
  write: () => FBO;
  swap: () => void;
}

interface ShaderProgram {
  program: WebGLProgram;
  uniforms: Uniforms;
}

function u(uniforms: Uniforms, name: string): WebGLUniformLocation | null {
  return uniforms[name] ?? null;
}

function createWebGLContext(canvas: HTMLCanvasElement) {
  const gl = canvas.getContext("webgl");
  if (!gl) return null;

  gl.getExtension("OES_texture_float");

  const compileShader = (source: string, type: number): WebGLShader | null => {
    const shader = gl.createShader(type);
    if (!shader) return null;

    gl.shaderSource(shader, source);
    gl.compileShader(shader);

    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      gl.deleteShader(shader);
      return null;
    }
    return shader;
  };

  const vertexShader = compileShader(SHADERS.vertex, gl.VERTEX_SHADER);
  if (!vertexShader) return null;

  const createProgram = (fragSource: string): ShaderProgram | null => {
    const fragShader = compileShader(fragSource, gl.FRAGMENT_SHADER);
    if (!fragShader) return null;

    const program = gl.createProgram();
    if (!program) return null;

    gl.attachShader(program, vertexShader);
    gl.attachShader(program, fragShader);
    gl.linkProgram(program);

    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return null;

    const uniforms: Record<string, WebGLUniformLocation | null> = {};
    const uniformCount = gl.getProgramParameter(program, gl.ACTIVE_UNIFORMS);

    for (let i = 0; i < uniformCount; i++) {
      const info = gl.getActiveUniform(program, i);
      if (info) {
        uniforms[info.name] = gl.getUniformLocation(program, info.name);
      }
    }

    return { program, uniforms };
  };

  const programs = {
    splat: createProgram(SHADERS.splat),
    divergence: createProgram(SHADERS.divergence),
    pressure: createProgram(SHADERS.pressure),
    gradientSubtract: createProgram(SHADERS.gradientSubtract),
    advection: createProgram(SHADERS.advection),
    output: createProgram(SHADERS.output),
  };

  const allProgramsValid = Object.values(programs).every(Boolean);
  if (!allProgramsValid) return null;

  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(
    gl.ARRAY_BUFFER,
    new Float32Array([-1, -1, -1, 1, 1, 1, 1, -1]),
    gl.STATIC_DRAW
  );
  gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(
    gl.ELEMENT_ARRAY_BUFFER,
    new Uint16Array([0, 1, 2, 0, 2, 3]),
    gl.STATIC_DRAW
  );
  gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
  gl.enableVertexAttribArray(0);

  const createFBO = (w: number, h: number, type: number = gl.RGBA): FBO => {
    gl.activeTexture(gl.TEXTURE0);

    const texture = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texImage2D(gl.TEXTURE_2D, 0, type, w, h, 0, type, gl.FLOAT, null);

    const fbo = gl.createFramebuffer()!;
    gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
    gl.framebufferTexture2D(
      gl.FRAMEBUFFER,
      gl.COLOR_ATTACHMENT0,
      gl.TEXTURE_2D,
      texture,
      0
    );
    gl.viewport(0, 0, w, h);
    gl.clear(gl.COLOR_BUFFER_BIT);

    return {
      fbo,
      width: w,
      height: h,
      attach(id: number) {
        gl.activeTexture(gl.TEXTURE0 + id);
        gl.bindTexture(gl.TEXTURE_2D, texture);
        return id;
      },
    };
  };

  const createDoubleFBO = (w: number, h: number, type: number = gl.RGBA): DoubleFBO => {
    let fbo1 = createFBO(w, h, type);
    let fbo2 = createFBO(w, h, type);

    return {
      width: w,
      height: h,
      texelSizeX: 1 / w,
      texelSizeY: 1 / h,
      read: () => fbo1,
      write: () => fbo2,
      swap() {
        [fbo1, fbo2] = [fbo2, fbo1];
      },
    };
  };

  const blit = (target: FBO | null) => {
    if (target) {
      gl.viewport(0, 0, target.width, target.height);
      gl.bindFramebuffer(gl.FRAMEBUFFER, target.fbo);
    } else {
      gl.viewport(0, 0, gl.drawingBufferWidth, gl.drawingBufferHeight);
      gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    }
    gl.drawElements(gl.TRIANGLES, 6, gl.UNSIGNED_SHORT, 0);
  };

  return {
    gl,
    programs: programs as { [K in keyof typeof programs]: ShaderProgram },
    createFBO,
    createDoubleFBO,
    blit,
  };
}

export function FluidCursor({
  color = { r: 0.21, g: 0.18, b: 0.51 },
  className = "",
}: FluidCursorProps): ReactNode {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = createWebGLContext(canvas);
    if (!ctx) return;

    const { gl, programs, createDoubleFBO, createFBO, blit } = ctx;

    const pointer = { x: 0, y: 0, dx: 0, dy: 0, moved: false };
    let isPreview = true;
    let pointerSize = 4 / window.innerHeight;

    let outputColor: DoubleFBO;
    let velocity: DoubleFBO;
    let divergenceFBO: FBO;
    let pressure: DoubleFBO;

    const initFBOs = () => {
      const w = Math.floor(0.25 * canvas.width);
      const h = Math.floor(0.25 * canvas.height);

      outputColor = createDoubleFBO(w, h);
      velocity = createDoubleFBO(w, h);
      divergenceFBO = createFBO(w, h, gl.RGB);
      pressure = createDoubleFBO(w, h, gl.RGB);
    };

    const resize = () => {
      pointerSize = 4 / window.innerHeight;
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      initFBOs();
    };

    const updatePointer = (x: number, y: number) => {
      pointer.moved = true;
      pointer.dx = 5 * (x - pointer.x);
      pointer.dy = 5 * (y - pointer.y);
      pointer.x = x;
      pointer.y = y;
    };

    const onMouseMove = (e: MouseEvent) => {
      isPreview = false;
      updatePointer(e.pageX, e.pageY);
    };

    const onTouchMove = (e: TouchEvent) => {
      isPreview = false;
      const touch = e.targetTouches[0];
      if (touch) updatePointer(touch.pageX, touch.pageY);
    };

    const render = (t: number) => {
      const dt = 1 / 60;

      if (t && isPreview) {
        const x =
          0.5 +
          0.25 * Math.sin(0.0017 * t) +
          0.12 * Math.sin(0.0031 * t + 1.3) +
          0.08 * Math.cos(0.0053 * t + 2.7) +
          0.05 * Math.sin(0.0079 * t + 4.1);

        const y =
          0.5 +
          0.18 * Math.sin(0.0023 * t + 0.5) +
          0.12 * Math.cos(0.0041 * t + 1.8) +
          0.08 * Math.sin(0.0067 * t + 3.2) +
          0.05 * Math.cos(0.0089 * t + 5.0);

        updatePointer(x * window.innerWidth, y * window.innerHeight);
      }

      if (pointer.moved) {
        if (!isPreview) pointer.moved = false;

        const { splat } = programs;
        gl.useProgram(splat.program);
        gl.uniform1i(u(splat.uniforms, "u_input_texture"), velocity.read().attach(1));
        gl.uniform1f(u(splat.uniforms, "u_ratio"), canvas.width / canvas.height);
        gl.uniform2f(
          u(splat.uniforms, "u_point"),
          pointer.x / canvas.width,
          1 - pointer.y / canvas.height
        );
        gl.uniform3f(u(splat.uniforms, "u_point_value"), pointer.dx, -pointer.dy, 1);
        gl.uniform1f(u(splat.uniforms, "u_point_size"), pointerSize);
        blit(velocity.write());
        velocity.swap();

        gl.uniform1i(
          u(splat.uniforms, "u_input_texture"),
          outputColor.read().attach(1)
        );
        gl.uniform3f(
          u(splat.uniforms, "u_point_value"),
          1 - color.r,
          1 - color.g,
          1 - color.b
        );
        blit(outputColor.write());
        outputColor.swap();
      }

      const { divergence, pressure: pressureProg, gradientSubtract, advection, output } = programs;

      gl.useProgram(divergence.program);
      gl.uniform2f(u(divergence.uniforms, "u_texel"), velocity.texelSizeX, velocity.texelSizeY);
      gl.uniform1i(u(divergence.uniforms, "u_velocity_texture"), velocity.read().attach(1));
      blit(divergenceFBO);

      gl.useProgram(pressureProg.program);
      gl.uniform2f(u(pressureProg.uniforms, "u_texel"), velocity.texelSizeX, velocity.texelSizeY);
      gl.uniform1i(u(pressureProg.uniforms, "u_divergence_texture"), divergenceFBO.attach(1));

      for (let i = 0; i < 4; i++) {
        gl.uniform1i(u(pressureProg.uniforms, "u_pressure_texture"), pressure.read().attach(2));
        blit(pressure.write());
        pressure.swap();
      }

      gl.useProgram(gradientSubtract.program);
      gl.uniform2f(u(gradientSubtract.uniforms, "u_texel"), velocity.texelSizeX, velocity.texelSizeY);
      gl.uniform1i(u(gradientSubtract.uniforms, "u_pressure_texture"), pressure.read().attach(1));
      gl.uniform1i(u(gradientSubtract.uniforms, "u_velocity_texture"), velocity.read().attach(2));
      blit(velocity.write());
      velocity.swap();

      gl.useProgram(advection.program);
      gl.uniform2f(u(advection.uniforms, "u_texel"), velocity.texelSizeX, velocity.texelSizeY);
      gl.uniform1i(u(advection.uniforms, "u_velocity_texture"), velocity.read().attach(1));
      gl.uniform1i(u(advection.uniforms, "u_input_texture"), velocity.read().attach(1));
      gl.uniform1f(u(advection.uniforms, "u_dt"), dt);
      blit(velocity.write());
      velocity.swap();

      gl.useProgram(advection.program);
      gl.uniform2f(u(advection.uniforms, "u_texel"), outputColor.texelSizeX, outputColor.texelSizeY);
      gl.uniform1i(u(advection.uniforms, "u_input_texture"), outputColor.read().attach(2));
      blit(outputColor.write());
      outputColor.swap();

      gl.useProgram(output.program);
      gl.uniform1i(u(output.uniforms, "u_output_texture"), outputColor.read().attach(1));
      blit(null);

      animationRef.current = requestAnimationFrame(render);
    };

    resize();
    window.addEventListener("resize", resize);
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("touchmove", onTouchMove, { passive: false });
    animationRef.current = requestAnimationFrame(render);

    return () => {
      window.removeEventListener("resize", resize);
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("touchmove", onTouchMove);
      cancelAnimationFrame(animationRef.current);
    };
  }, [color]);

  return (
    <canvas
      ref={canvasRef}
      className={`pointer-events-none mix-blend-multiply blur ${className}`}
      aria-hidden="true"
    />
  );
}
