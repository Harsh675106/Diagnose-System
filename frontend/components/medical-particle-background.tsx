"use client";

import { useEffect, useRef } from "react";

interface MedicalParticleBackgroundProps {
  className?: string;
  intensity?: "low" | "medium" | "high";
  theme?: "medical" | "dark" | "shiny";
}

type SmokeWisp = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  life: number;
  maxLife: number;
  size: number;
  rotation: number;
  spin: number;
};

const intensityConfig = {
  low: { amplitude: 0.9, cycleMs: 6200, wispsPerFrame: 1, glow: 14 },
  medium: { amplitude: 1, cycleMs: 5400, wispsPerFrame: 2, glow: 18 },
  high: { amplitude: 1.08, cycleMs: 4700, wispsPerFrame: 3, glow: 22 },
} as const;

const themeConfig = {
  medical: {
    line: "#4b5563",
    lineSoft: "rgba(75, 85, 99, 0.1)",
    glow: "rgba(107, 114, 128, 0.12)",
    smoke: "156, 163, 175",
    flare: "rgba(156, 163, 175, 0.08)",
  },
  dark: {
    line: "#374151",
    lineSoft: "rgba(55, 65, 81, 0.11)",
    glow: "rgba(107, 114, 128, 0.14)",
    smoke: "107, 114, 128",
    flare: "rgba(148, 163, 184, 0.09)",
  },
  shiny: {
    line: "#3f3f46",
    lineSoft: "rgba(63, 63, 70, 0.1)",
    glow: "rgba(113, 113, 122, 0.14)",
    smoke: "161, 161, 170",
    flare: "rgba(161, 161, 170, 0.08)",
  },
} as const;

function heartbeatValueAt(progress: number, amplitude: number) {
  if (progress < 0.26) return 0;
  if (progress < 0.31) return -0.22 * amplitude * ((progress - 0.26) / 0.05);
  if (progress < 0.34) return -0.22 * amplitude * (1 - (progress - 0.31) / 0.03);
  if (progress < 0.39) return 0;
  if (progress < 0.43) return 0.58 * amplitude * ((progress - 0.39) / 0.04);
  if (progress < 0.47) return 0.58 * amplitude * (1 - (progress - 0.43) / 0.04);
  if (progress < 0.51) return -1.5 * amplitude * ((progress - 0.47) / 0.04);
  if (progress < 0.55) return -1.5 * amplitude + 3.1 * amplitude * ((progress - 0.51) / 0.04);
  if (progress < 0.6) return 1.6 * amplitude - 2.18 * amplitude * ((progress - 0.55) / 0.05);
  if (progress < 0.66) return -0.58 * amplitude * (1 - (progress - 0.6) / 0.06);
  if (progress < 0.73) return 0;
  if (progress < 0.78) return 0.34 * amplitude * ((progress - 0.73) / 0.05);
  if (progress < 0.84) return 0.34 * amplitude * (1 - (progress - 0.78) / 0.06);
  return 0;
}

function pointOnHeartbeat(progress: number, width: number, height: number, amplitude: number) {
  const paddingX = width * 0.08;
  const usableWidth = width - paddingX * 2;
  const x = paddingX + progress * usableWidth;
  const baseline = height * 0.6;
  const beatScale = Math.min(height * 0.14, 128) * amplitude;
  const y = baseline - heartbeatValueAt(progress, amplitude) * beatScale;
  return { x, y };
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

export function MedicalParticleBackground({
  className = "",
  intensity = "medium",
  theme = "medical",
}: MedicalParticleBackgroundProps) {
  return (
    <MedicalParticleRingCanvas
      className={className}
      intensity={intensity}
      theme={theme}
    />
  );
}

export function MedicalParticleRingCanvas({
  className = "",
  intensity = "medium",
  theme = "dark",
}: MedicalParticleBackgroundProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number | null>(null);
  const wispsRef = useRef<SmokeWisp[]>([]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const config = intensityConfig[intensity];
    const palette = themeConfig[theme];

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      const width = window.innerWidth;
      const height = window.innerHeight;

      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const spawnWisp = (x: number, y: number, energy: number) => {
      const spread = 10 + energy * 18;
      wispsRef.current.push({
        x: x + (Math.random() - 0.5) * spread,
        y: y + (Math.random() - 0.5) * spread * 1.5,
        vx: (Math.random() - 0.5) * 0.22,
        vy: -0.12 - Math.random() * 0.28,
        life: 0,
        maxLife: 820 + Math.random() * 560,
        size: 18 + Math.random() * 22 + energy * 10,
        rotation: Math.random() * Math.PI * 2,
        spin: (Math.random() - 0.5) * 0.004,
      });
    };

    const drawBackgroundGlow = (width: number, height: number, sweepPoint: { x: number; y: number }) => {
      const centerGlow = ctx.createRadialGradient(
        width * 0.5,
        height * 0.6,
        0,
        width * 0.5,
        height * 0.6,
        Math.min(width * 0.28, 300),
      );
      centerGlow.addColorStop(0, "rgba(148, 163, 184, 0.035)");
      centerGlow.addColorStop(0.45, "rgba(203, 213, 225, 0.03)");
      centerGlow.addColorStop(1, "rgba(255,255,255,0)");
      ctx.fillStyle = centerGlow;
      ctx.fillRect(0, 0, width, height);

      const sweepGlow = ctx.createRadialGradient(
        sweepPoint.x,
        sweepPoint.y,
        0,
        sweepPoint.x,
        sweepPoint.y,
        70,
      );
      sweepGlow.addColorStop(0, palette.flare);
      sweepGlow.addColorStop(0.58, "rgba(203, 213, 225, 0.035)");
      sweepGlow.addColorStop(1, "rgba(255,255,255,0)");
      ctx.fillStyle = sweepGlow;
      ctx.beginPath();
      ctx.arc(sweepPoint.x, sweepPoint.y, 130, 0, Math.PI * 2);
      ctx.fill();
    };

    const drawSmoke = (delta: number) => {
      wispsRef.current = wispsRef.current.filter((wisp) => {
        wisp.life += delta;
        if (wisp.life >= wisp.maxLife) return false;

        wisp.x += wisp.vx * delta;
        wisp.y += wisp.vy * delta;
        wisp.rotation += wisp.spin * delta;

        const age = wisp.life / wisp.maxLife;
        const alpha = (1 - age) * 0.1;
        const stretchX = wisp.size * (1.2 + age * 1.8);
        const stretchY = wisp.size * (0.55 + age * 1.1);

        ctx.save();
        ctx.translate(wisp.x, wisp.y);
        ctx.rotate(wisp.rotation);
        ctx.scale(stretchX, stretchY);

        const smoke = ctx.createRadialGradient(0, 0, 0.1, 0, 0, 1);
        smoke.addColorStop(0, `rgba(${palette.smoke}, ${alpha})`);
        smoke.addColorStop(0.42, `rgba(${palette.smoke}, ${alpha * 0.48})`);
        smoke.addColorStop(1, `rgba(${palette.smoke}, 0)`);
        ctx.fillStyle = smoke;
        ctx.beginPath();
        ctx.arc(0, 0, 1, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();

        return true;
      });
    };

    const drawHeartbeat = (sweep: number, width: number, height: number, amplitude: number) => {
      const baseline = pointOnHeartbeat(0, width, height, amplitude).y;
      const startX = width * 0.08;
      const endX = width * 0.92;
      const sweepX = startX + (endX - startX) * sweep;

      ctx.save();
      ctx.lineCap = "round";
      ctx.lineJoin = "round";

      ctx.strokeStyle = "rgba(255,255,255,0.22)";
      ctx.lineWidth = 2.2;
      ctx.beginPath();
      ctx.moveTo(startX, baseline);
      ctx.lineTo(endX, baseline);
      ctx.stroke();

      const glowPath = new Path2D();
      for (let i = 0; i <= 320; i += 1) {
        const progress = i / 320;
        if (progress > sweep) break;
        const point = pointOnHeartbeat(progress, width, height, amplitude);
        if (i === 0) glowPath.moveTo(point.x, point.y);
        else glowPath.lineTo(point.x, point.y);
      }

      ctx.shadowBlur = config.glow;
      ctx.shadowColor = palette.glow;
      ctx.strokeStyle = "rgba(148, 163, 184, 0.11)";
      ctx.lineWidth = 4.8;
      ctx.stroke(glowPath);

      const lineGradient = ctx.createLinearGradient(startX, 0, sweepX, 0);
      lineGradient.addColorStop(0, palette.lineSoft);
      lineGradient.addColorStop(Math.max(0, sweep - 0.28), "rgba(107, 114, 128, 0.42)");
      lineGradient.addColorStop(1, palette.line);

      ctx.strokeStyle = lineGradient;
      ctx.lineWidth = 2.2;
      ctx.stroke(glowPath);

      ctx.beginPath();
      ctx.fillStyle = palette.line;
      ctx.arc(sweepX, pointOnHeartbeat(sweep, width, height, amplitude).y, 2.6, 0, Math.PI * 2);
      ctx.fill();

      ctx.restore();
    };

    resize();
    window.addEventListener("resize", resize);

    let lastTime = performance.now();

    const animate = (now: number) => {
      const delta = now - lastTime;
      lastTime = now;

      const width = window.innerWidth;
      const height = window.innerHeight;
      const sweep = ((now % config.cycleMs) / config.cycleMs);
      const amplitude = config.amplitude * (1 + Math.sin(now * 0.0022) * 0.015);
      const sweepPoint = pointOnHeartbeat(sweep, width, height, amplitude);
      const energy = clamp(Math.abs(heartbeatValueAt(sweep, amplitude)), 0, 1.6);

      ctx.clearRect(0, 0, width, height);
      drawBackgroundGlow(width, height, sweepPoint);

      for (let i = 0; i < config.wispsPerFrame; i += 1) {
        spawnWisp(sweepPoint.x, sweepPoint.y, energy);
        if (energy > 0.6) {
          spawnWisp(sweepPoint.x, sweepPoint.y, energy + 0.2);
        }
      }

      ctx.globalCompositeOperation = "lighter";
      drawSmoke(delta);
      ctx.globalCompositeOperation = "source-over";
      drawHeartbeat(sweep, width, height, amplitude);

      animationRef.current = requestAnimationFrame(animate);
    };

    animationRef.current = requestAnimationFrame(animate);

    return () => {
      window.removeEventListener("resize", resize);
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
    };
  }, [intensity, theme]);

  return (
    <div className={`absolute inset-0 ${className}`}>
      <canvas
        ref={canvasRef}
        className="h-full w-full"
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          zIndex: 0,
          pointerEvents: "none",
        }}
      />
    </div>
  );
}

export function MedicalRingBackground({
  className = "",
  intensity = "medium",
  theme = "dark",
}: MedicalParticleBackgroundProps) {
  return (
    <MedicalParticleRingCanvas
      className={className}
      intensity={intensity}
      theme={theme}
    />
  );
}

export default MedicalParticleRingCanvas;
