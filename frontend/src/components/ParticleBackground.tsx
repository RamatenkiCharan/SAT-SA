import React, { useEffect, useRef } from "react";

interface Particle3D {
  // 3D Space Coordinates (Origin centered at screen midpoint)
  x: number;
  y: number;
  z: number; // -280 (closest to camera) to +580 (deep background)

  // 3D Velocities
  vx: number;
  vy: number;
  vz: number;
  baseVx: number;
  baseVy: number;
  baseVz: number;

  // Visual Properties
  baseRadius: number;
  currentRadius: number;
  targetRadius: number;
  baseOpacity: number;
  currentOpacity: number;
  targetOpacity: number;

  // 3D Orbital Sway Phases (Multi-frequency organic floating)
  swayPhaseX: number;
  swaySpeedX: number;
  swayAmpX: number;
  swayPhaseY: number;
  swaySpeedY: number;
  swayAmpY: number;
  swayPhaseZ: number;
  swaySpeedZ: number;
  swayAmpZ: number;

  // Subtle Luminance Pulse
  pulsePhase: number;
  pulseSpeed: number;

  // Interactive Glow Halo
  glowIntensity: number;
  targetGlow: number;
}

export interface ParticleBackgroundProps {
  className?: string;
  active?: boolean; // Only active on Landing Page & Executive Overview
}

/**
 * ParticleBackground: High-Fidelity 3D Antigravity Particle Environment
 *
 * Implements a true 3D spatial field of floating white micro-particles with:
 * - Perspective projection (FOV 500)
 * - 3D zero-gravity floating drift and multi-axis sinusoidal sway
 * - Dynamic 3D camera parallax responding smoothly to cursor position
 * - Localized 3D cursor interaction (gentle liquid deflection, smooth 1mm growth, soft halo)
 * - Automatic pause / fade when navigating away from Landing & Overview
 * - 100% pointer-events: none and full UI protection
 */
export const ParticleBackground: React.FC<ParticleBackgroundProps> = ({
  className,
  active = true,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;

    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;

    let animationFrameId: number;
    let dpr = window.devicePixelRatio || 1;
    let width = 0;
    let height = 0;
    let centerX = 0;
    let centerY = 0;

    // Responsive 3D particle counts
    const getParticleCount = (w: number, h: number): number => {
      const area = w * h;
      if (w >= 1440) return Math.min(Math.max(Math.floor(area / 6000), 280), 380); // Desktop: 280-380
      if (w >= 1024) return Math.min(Math.max(Math.floor(area / 5600), 200), 290); // Laptop: 200-290
      if (w >= 640)  return Math.min(Math.max(Math.floor(area / 5000), 130), 210); // Tablet: 130-210
      return Math.min(Math.max(Math.floor(area / 4400), 85), 140);                // Mobile: 85-140
    };

    const resizeCanvas = () => {
      dpr = window.devicePixelRatio || 1;
      width = canvas.width = window.innerWidth * dpr;
      height = canvas.height = window.innerHeight * dpr;
      centerX = width / 2;
      centerY = height / 2;
    };
    resizeCanvas();

    const targetCount = getParticleCount(window.innerWidth, window.innerHeight);
    const particles: Particle3D[] = [];

    // 3D Volume boundaries
    const boundX = width * 0.9;
    const boundY = height * 0.9;
    const zMin = -280;
    const zMax = 580;
    const FOV = 500;

    for (let i = 0; i < targetCount; i++) {
      const z = Math.random() * (zMax - zMin) + zMin;
      // Normalized depth 0 (nearest) to 1 (deepest)
      const depthRatio = (z - zMin) / (zMax - zMin);

      let baseRadius: number;
      let baseOpacity: number;
      let baseVy: number;

      if (depthRatio < 0.35) {
        // Near / Foreground: 2.0–3.0 px
        baseRadius = (2.0 + Math.random() * 1.0) * dpr;
        baseOpacity = 0.55 + Math.random() * 0.20;
        baseVy = -(0.18 + Math.random() * 0.12) * dpr;
      } else if (depthRatio < 0.70) {
        // Midground: 1.5–2.5 px
        baseRadius = (1.5 + Math.random() * 1.0) * dpr;
        baseOpacity = 0.35 + Math.random() * 0.20;
        baseVy = -(0.10 + Math.random() * 0.10) * dpr;
      } else {
        // Deep Background: 1.0–1.5 px
        baseRadius = (1.0 + Math.random() * 0.5) * dpr;
        baseOpacity = 0.20 + Math.random() * 0.15;
        baseVy = -(0.05 + Math.random() * 0.07) * dpr;
      }

      particles.push({
        x: (Math.random() - 0.5) * boundX * 2,
        y: (Math.random() - 0.5) * boundY * 2,
        z,
        vx: 0,
        vy: 0,
        vz: 0,
        baseVx: (Math.random() - 0.5) * 0.08 * dpr,
        baseVy,
        baseVz: (Math.random() - 0.5) * 0.12 * dpr,
        baseRadius,
        currentRadius: baseRadius,
        targetRadius: baseRadius,
        baseOpacity,
        currentOpacity: baseOpacity,
        targetOpacity: baseOpacity,
        swayPhaseX: Math.random() * Math.PI * 2,
        swaySpeedX: Math.random() * 0.007 + 0.003,
        swayAmpX: (Math.random() * 0.35 + 0.15) * dpr,
        swayPhaseY: Math.random() * Math.PI * 2,
        swaySpeedY: Math.random() * 0.006 + 0.003,
        swayAmpY: (Math.random() * 0.25 + 0.10) * dpr,
        swayPhaseZ: Math.random() * Math.PI * 2,
        swaySpeedZ: Math.random() * 0.005 + 0.002,
        swayAmpZ: (Math.random() * 0.4 + 0.2) * dpr,
        pulsePhase: Math.random() * Math.PI * 2,
        pulseSpeed: Math.random() * 0.01 + 0.004,
        glowIntensity: 0,
        targetGlow: 0,
      });
    }

    // Camera & Mouse Parallax Tracking
    const camera = {
      x: 0,
      y: 0,
      targetX: 0,
      targetY: 0,
    };

    const mouse = {
      screenX: -9999,
      screenY: -9999,
      targetScreenX: -9999,
      targetScreenY: -9999,
      radius: 140 * dpr,
      active: false,
    };

    const handleMouseMove = (e: MouseEvent) => {
      mouse.targetScreenX = e.clientX * dpr;
      mouse.targetScreenY = e.clientY * dpr;
      mouse.active = true;

      // Subtle 3D Camera Shift (Depth Parallax)
      const normX = (e.clientX * dpr - centerX) / centerX;
      const normY = (e.clientY * dpr - centerY) / centerY;
      camera.targetX = normX * 38 * dpr;
      camera.targetY = normY * 26 * dpr;
    };

    const handleMouseLeave = () => {
      mouse.targetScreenX = -9999;
      mouse.targetScreenY = -9999;
      mouse.active = false;
      camera.targetX = 0;
      camera.targetY = 0;
    };

    window.addEventListener("resize", resizeCanvas, { passive: true });
    window.addEventListener("mousemove", handleMouseMove, { passive: true });
    window.addEventListener("mouseleave", handleMouseLeave, { passive: true });

    // Static reduced-motion rendering
    if (prefersReducedMotion) {
      ctx.clearRect(0, 0, width, height);
      for (const p of particles) {
        const scale = FOV / (FOV + p.z);
        const projX = centerX + p.x * scale;
        const projY = centerY + p.y * scale;
        const projRadius = p.baseRadius * scale;
        ctx.beginPath();
        ctx.arc(projX, projY, Math.max(projRadius, 0.8 * dpr), 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255, 255, 255, ${p.baseOpacity * scale})`;
        ctx.fill();
      }
      return () => {
        window.removeEventListener("resize", resizeCanvas);
        window.removeEventListener("mousemove", handleMouseMove);
        window.removeEventListener("mouseleave", handleMouseLeave);
      };
    }

    // 3D Animation & Rendering Loop
    const render = () => {
      if (!active) {
        ctx.clearRect(0, 0, width, height);
        animationFrameId = requestAnimationFrame(render);
        return;
      }

      ctx.clearRect(0, 0, width, height);

      // Smooth camera parallax interpolation
      camera.x += (camera.targetX - camera.x) * 0.05;
      camera.y += (camera.targetY - camera.y) * 0.05;

      // Smooth cursor lerp
      if (mouse.active) {
        mouse.screenX += (mouse.targetScreenX - mouse.screenX) * 0.1;
        mouse.screenY += (mouse.targetScreenY - mouse.screenY) * 0.1;
      }

      const pCount = particles.length;

      // 1. Update 3D Physics and Screen Projections
      for (let i = 0; i < pCount; i++) {
        const p = particles[i];

        // Multi-axis 3D organic sinusoidal sway
        p.swayPhaseX += p.swaySpeedX;
        p.swayPhaseY += p.swaySpeedY;
        p.swayPhaseZ += p.swaySpeedZ;

        const swayX = Math.sin(p.swayPhaseX) * p.swayAmpX;
        const swayY = Math.cos(p.swayPhaseY) * p.swayAmpY;
        const swayZ = Math.sin(p.swayPhaseZ) * p.swayAmpZ;

        // Apply 3D zero-gravity velocities
        p.x += p.baseVx + p.vx + swayX;
        p.y += p.baseVy + p.vy + swayY;
        p.z += p.baseVz + p.vz + swayZ;

        // Velocity damping
        p.vx *= 0.93;
        p.vy *= 0.93;
        p.vz *= 0.93;

        // 3D Depth boundaries wrapping
        if (p.z < zMin) {
          p.z = zMax;
          p.x = (Math.random() - 0.5) * boundX * 2;
          p.y = (Math.random() - 0.5) * boundY * 2;
        } else if (p.z > zMax) {
          p.z = zMin;
        }

        // 3D X/Y spatial wrapping
        if (p.x < -boundX) p.x = boundX;
        else if (p.x > boundX) p.x = -boundX;

        if (p.y < -boundY) p.y = boundY;
        else if (p.y > boundY) p.y = -boundY;

        // Perspective Projection calculation (FOV 500)
        const scale = FOV / (FOV + p.z);
        const projX = centerX + (p.x - camera.x) * scale;
        const projY = centerY + (p.y - camera.y) * scale;

        // 3D Cursor Interaction in projected screen space
        if (mouse.active) {
          const mdx = projX - mouse.screenX;
          const mdy = projY - mouse.screenY;
          const mdist = Math.sqrt(mdx * mdx + mdy * mdy);

          if (mdist < mouse.radius && mdist > 0) {
            const proximity = 1 - mdist / mouse.radius; // 0 to 1
            const force = Math.pow(proximity, 1.8) * 2.2 * scale * dpr;
            const angle = Math.atan2(mdy, mdx);

            // Subtle 3D physical deflection (liquid yield)
            p.vx += Math.cos(angle) * force;
            p.vy += Math.sin(angle) * force;
            p.vz += proximity * 1.5 * dpr; // Gentle depth push

            // Smooth 3D growth (approx 1mm / ~4.0-4.5px max)
            const targetGrowth = (p.baseRadius + proximity * 2.2 * dpr) * scale;
            p.targetRadius = Math.min(targetGrowth, 4.5 * dpr);

            // Subtle brightness boost (0.70 to 0.90 max near cursor)
            p.targetOpacity = Math.min(p.baseOpacity + proximity * 0.35, 0.90);

            // Soft white atmospheric halo
            p.targetGlow = proximity * 0.8;
          } else {
            p.targetRadius = p.baseRadius * scale;
            p.targetOpacity = p.baseOpacity * scale;
            p.targetGlow = 0;
          }
        } else {
          p.targetRadius = p.baseRadius * scale;
          p.targetOpacity = p.baseOpacity * scale;
          p.targetGlow = 0;
        }

        // Smooth continuous interpolation for radius, opacity, and glow
        p.currentRadius += (p.targetRadius - p.currentRadius) * 0.08;
        p.currentOpacity += (p.targetOpacity - p.currentOpacity) * 0.08;
        p.glowIntensity += (p.targetGlow - p.glowIntensity) * 0.08;

        // Asynchronous subtle breathing pulse
        p.pulsePhase += p.pulseSpeed;
        const pulse = Math.sin(p.pulsePhase) * 0.12 + 0.88;
        const finalOpacity = Math.min(p.currentOpacity * pulse, 0.90);

        // Render pure white 3D particle
        if (p.glowIntensity > 0.05) {
          ctx.save();
          ctx.shadowBlur = 4 * p.glowIntensity * dpr;
          ctx.shadowColor = `rgba(255, 255, 255, ${p.glowIntensity * 0.5})`;
          ctx.beginPath();
          ctx.arc(projX, projY, Math.max(p.currentRadius, 0.8 * dpr), 0, Math.PI * 2);
          ctx.fillStyle = `rgba(255, 255, 255, ${finalOpacity})`;
          ctx.fill();
          ctx.restore();
        } else {
          ctx.beginPath();
          ctx.arc(projX, projY, Math.max(p.currentRadius, 0.8 * dpr), 0, Math.PI * 2);
          ctx.fillStyle = `rgba(255, 255, 255, ${finalOpacity})`;
          ctx.fill();
        }
      }

      animationFrameId = requestAnimationFrame(render);
    };

    animationFrameId = requestAnimationFrame(render);

    return () => {
      window.removeEventListener("resize", resizeCanvas);
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseleave", handleMouseLeave);
      cancelAnimationFrame(animationFrameId);
    };
  }, [active]);

  return (
    <canvas
      ref={canvasRef}
      className={className}
      aria-hidden="true"
      style={{
        position: "fixed",
        inset: 0,
        width: "100vw",
        height: "100vh",
        zIndex: 0,
        pointerEvents: "none",
        userSelect: "none",
        opacity: active ? 0.9 : 0,
        transition: "opacity 0.4s ease",
      }}
    />
  );
};

export default ParticleBackground;
