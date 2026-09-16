import React, { useEffect, useRef } from "react";

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  baseVx: number;
  baseVy: number;
  size: number;
  z: number;
  opacity: number;
  color: string;
  pulsePhase: number;
  pulseSpeed: number;
  swayAngle: number;
  swaySpeed: number;
  swayRadius: number;
}

export const CyberBackgroundCanvas: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    // Respect user preference for reduced motion
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReducedMotion) return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;

    let animationFrameId: number;
    let dpr = window.devicePixelRatio || 1;
    let width = (canvas.width = window.innerWidth * dpr);
    let height = (canvas.height = window.innerHeight * dpr);

    const handleResize = () => {
      if (!canvas) return;
      dpr = window.devicePixelRatio || 1;
      width = canvas.width = window.innerWidth * dpr;
      height = canvas.height = window.innerHeight * dpr;
    };
    window.addEventListener("resize", handleResize);

    const mouse = {
      x: -9999,
      y: -9999,
      targetX: -9999,
      targetY: -9999,
      radius: 140 * dpr,
      active: false,
    };

    const parallax = {
      x: 0,
      y: 0,
      targetX: 0,
      targetY: 0,
    };

    const handleMouseMove = (e: MouseEvent) => {
      mouse.targetX = e.clientX * dpr;
      mouse.targetY = e.clientY * dpr;
      mouse.active = true;

      const centerX = (window.innerWidth / 2) * dpr;
      const centerY = (window.innerHeight / 2) * dpr;
      parallax.targetX = ((e.clientX * dpr - centerX) / centerX) * 18 * dpr;
      parallax.targetY = ((e.clientY * dpr - centerY) / centerY) * 18 * dpr;
    };

    const handleMouseLeave = () => {
      mouse.targetX = -9999;
      mouse.targetY = -9999;
      mouse.active = false;
      parallax.targetX = 0;
      parallax.targetY = 0;
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseleave", handleMouseLeave);

    // Calm, professional supervisory palette
    const colors = [
      "rgba(0, 240, 255, ",   // Cyan
      "rgba(56, 189, 248, ",  // Sky Blue
      "rgba(16, 185, 129, ",  // Emerald
      "rgba(148, 163, 184, ", // Slate / Muted
    ];

    const particleCount = Math.min(Math.floor((window.innerWidth * window.innerHeight) / 7500), 160);
    const particles: Particle[] = [];

    for (let i = 0; i < particleCount; i++) {
      const z = Math.random() * 0.75 + 0.25;
      const color = colors[Math.floor(Math.random() * colors.length)];

      particles.push({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: 0,
        vy: 0,
        baseVy: -(Math.random() * 0.25 + 0.1) * z * dpr,
        baseVx: (Math.random() - 0.5) * 0.12 * z * dpr,
        size: (Math.random() * 1.4 + 0.75) * z * dpr,
        z,
        opacity: (Math.random() * 0.35 + 0.2) * z,
        color,
        pulsePhase: Math.random() * Math.PI * 2,
        pulseSpeed: Math.random() * 0.015 + 0.005,
        swayAngle: Math.random() * Math.PI * 2,
        swaySpeed: Math.random() * 0.01 + 0.004,
        swayRadius: (Math.random() * 0.3 + 0.15) * dpr,
      });
    }

    const render = () => {
      ctx.clearRect(0, 0, width, height);

      mouse.x += (mouse.targetX - mouse.x) * 0.1;
      mouse.y += (mouse.targetY - mouse.y) * 0.1;
      parallax.x += (parallax.targetX - parallax.x) * 0.03;
      parallax.y += (parallax.targetY - parallax.y) * 0.03;

      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];

        p.swayAngle += p.swaySpeed;
        const swayX = Math.sin(p.swayAngle) * p.swayRadius;

        p.y += p.baseVy + p.vy;
        p.x += p.baseVx + p.vx + swayX;

        p.vx *= 0.94;
        p.vy *= 0.94;

        if (mouse.active) {
          const pDisplayX = p.x + parallax.x * p.z;
          const pDisplayY = p.y + parallax.y * p.z;
          const mdx = pDisplayX - mouse.x;
          const mdy = pDisplayY - mouse.y;
          const mdist = Math.sqrt(mdx * mdx + mdy * mdy);

          if (mdist < mouse.radius && mdist > 0) {
            const force = (1 - mdist / mouse.radius) * 1.8 * p.z * dpr;
            const angle = Math.atan2(mdy, mdx);
            p.vx += Math.cos(angle) * force;
            p.vy += Math.sin(angle) * force;
          }
        }

        if (p.y < -20 * dpr) {
          p.y = height + 20 * dpr;
          p.x = Math.random() * width;
        } else if (p.y > height + 20 * dpr) {
          p.y = -20 * dpr;
        }

        if (p.x < -20 * dpr) p.x = width + 20 * dpr;
        else if (p.x > width + 20 * dpr) p.x = -20 * dpr;

        p.pulsePhase += p.pulseSpeed;
        const pulse = Math.sin(p.pulsePhase) * 0.2 + 0.8;
        const currentOpacity = Math.min(p.opacity * pulse, 0.75);

        const renderX = p.x + parallax.x * p.z;
        const renderY = p.y + parallax.y * p.z;

        ctx.beginPath();
        ctx.arc(renderX, renderY, p.size, 0, Math.PI * 2);
        ctx.fillStyle = `${p.color}${currentOpacity})`;
        ctx.fill();
      }

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener("resize", handleResize);
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseleave", handleMouseLeave);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        width: "100vw",
        height: "100vh",
        zIndex: 0,
        pointerEvents: "none",
        opacity: 0.75,
      }}
    />
  );
};
