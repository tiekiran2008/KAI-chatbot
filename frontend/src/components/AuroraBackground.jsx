import { useEffect, useRef } from 'react';
import '@/styles/aurora.css';

/**
 * AuroraBackground renders a full-screen canvas with animated aurora effect.
 * It updates CSS custom properties --mouse-x and --mouse-y for gradient distortion.
 */
export default function AuroraBackground() {
  const canvasRef = useRef(null);
  const mouse = useRef({ x: 0.5, y: 0.5 }); // normalized (0-1)

  const updateCSS = () => {
    const parent = canvasRef.current?.parentElement;
    if (parent) {
      parent.style.setProperty('--mouse-x', `${mouse.current.x * 100}%`);
      parent.style.setProperty('--mouse-y', `${mouse.current.y * 100}%`);
    }
  };

  const handlePointerMove = (e) => {
    const rect = canvasRef.current?.parentElement?.getBoundingClientRect();
    if (!rect) return;
    mouse.current = {
      x: (e.clientX - rect.left) / rect.width,
      y: (e.clientY - rect.top) / rect.height,
    };
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animationId;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener('resize', resize);
    window.addEventListener('pointermove', handlePointerMove);

    const draw = () => {
      const time = Date.now() * 0.001;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      for (let i = 0; i < 6; i++) {
        const hue = (time * 20 + i * 60) % 360;
        const gradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
        gradient.addColorStop(0, `hsl(${hue}, 80%, 60%)`);
        gradient.addColorStop(1, `hsl(${(hue + 60) % 360}, 80%, 40%)`);
        ctx.fillStyle = gradient;
        const offsetX = Math.sin(time + i) * 200 * (i + 1);
        const offsetY = Math.cos(time + i) * 150 * (i + 1);
        ctx.globalAlpha = 0.12;
        ctx.beginPath();
        ctx.arc(canvas.width / 2 + offsetX, canvas.height / 2 + offsetY, canvas.width * 0.7, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;
      updateCSS();
      animationId = requestAnimationFrame(draw);
    };
    draw();

    return () => {
      cancelAnimationFrame(animationId);
      window.removeEventListener('resize', resize);
      window.removeEventListener('pointermove', handlePointerMove);
    };
  }, []);

  return (
    <div className="aurora-bg">
      <canvas ref={canvasRef} className="absolute inset-0 w-full h-full" />
    </div>
  );
  const mouse = useRef({ x: 0.5, y: 0.5 }); // normalized (0-1)

  const updateCSS = () => {
    const parent = canvasRef.current?.parentElement;
    if (parent) {
      parent.style.setProperty('--mouse-x', `${mouse.current.x * 100}%`);
      parent.style.setProperty('--mouse-y', `${mouse.current.y * 100}%`);
    }
  };

  const handlePointerMove = (e) => {
    const rect = canvasRef.current?.parentElement?.getBoundingClientRect();
    if (!rect) return;
    mouse.current = {
      x: (e.clientX - rect.left) / rect.width,
      y: (e.clientY - rect.top) / rect.height,
    };
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animationId;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener('resize', resize);
    window.addEventListener('pointermove', handlePointerMove);

    const draw = () => {
      const time = Date.now() * 0.001;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      for (let i = 0; i < 6; i++) {
        const hue = (time * 20 + i * 60) % 360;
        const gradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
        gradient.addColorStop(0, `hsl(${hue}, 80%, 60%)`);
        gradient.addColorStop(1, `hsl(${(hue + 60) % 360}, 80%, 40%)`);
        ctx.fillStyle = gradient;
        const offsetX = Math.sin(time + i) * 200 * (i + 1);
        const offsetY = Math.cos(time + i) * 150 * (i + 1);
        ctx.globalAlpha = 0.12;
        ctx.beginPath();
        ctx.arc(canvas.width / 2 + offsetX, canvas.height / 2 + offsetY, canvas.width * 0.7, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;
      updateCSS();
      animationId = requestAnimationFrame(draw);
    };
    draw();

    return () => {
      cancelAnimationFrame(animationId);
      window.removeEventListener('resize', resize);
      window.removeEventListener('pointermove', handlePointerMove);
    };
  }, []);

  return (
    <div className="aurora-bg">
      <canvas ref={canvasRef} className="absolute inset-0 w-full h-full" />
    </div>
  );
}

import '@/styles/aurora.css';

/**
 * AuroraBackground renders a full-screen canvas with animated aurora effect.
 * It updates CSS custom properties --mouse-x and --mouse-y for gradient distortion.
 */
const AuroraBackground = () => {
  const canvasRef = useRef(null);
  const mouse = useRef({ x: 0.5, y: 0.5 }); // normalized (0-1)

  // Update CSS variables for mouse position
  const updateCSS = () => {
    const parent = canvasRef.current?.parentElement;
    if (parent) {
      parent.style.setProperty('--mouse-x', `${mouse.current.x * 100}%`);
      parent.style.setProperty('--mouse-y', `${mouse.current.y * 100}%`);
    }
  };

  // Interpolate mouse smoothly
  const lerp = (a, b, f) => a + (b - a) * f;

  const handlePointerMove = e => {
    const rect = canvasRef.current?.parentElement?.getBoundingClientRect();
    if (!rect) return;
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;
    mouse.current = { x, y };
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animationFrameId;
    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener('resize', resize);
    window.addEventListener('pointermove', handlePointerMove);

    const draw = () => {
      // Smooth mouse movement
      const current = mouse.current;
      const targetX = current.x;
      const targetY = current.y;
      // Simple noise-based color bands for aurora effect
      const time = Date.now() * 0.001;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      for (let i = 0; i < 6; i++) {
        const hue = (time * 20 + i * 60) % 360;
        const gradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
        gradient.addColorStop(0, `hsl(${hue}, 80%, 60%)`);
        gradient.addColorStop(1, `hsl(${(hue + 60) % 360}, 80%, 40%)`);
        ctx.fillStyle = gradient;
        const offsetX = Math.sin(time + i) * 200 * (i + 1);
        const offsetY = Math.cos(time + i) * 150 * (i + 1);
        ctx.globalAlpha = 0.12;
        ctx.beginPath();
        ctx.arc(canvas.width / 2 + offsetX, canvas.height / 2 + offsetY, canvas.width * 0.7, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;
      updateCSS();
      animationFrameId = requestAnimationFrame(draw);
    };
    draw();
    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('resize', resize);
      window.removeEventListener('pointermove', handlePointerMove);
    };
  }, []);

  return (
    <div className="aurora-bg">
      <canvas ref={canvasRef} className="absolute inset-0 w-full h-full" />
    </div>
  );
};

export default AuroraBackground;

/**
 * AuroraBackground renders a full‑screen canvas that displays an animated aurora‑borealis effect.
 * It tracks mouse movement with requestAnimationFrame for ultra‑smooth, low‑jank interaction.
 */
const AuroraBackground = () => {
  const canvasRef = useRef(null);
  const mouse = useRef({ x: 0.5, y: 0.5 }); // normalized (0‑1)
  const target = useRef({ x: 0.5, y: 0.5 });

  // Update CSS custom properties for gradient distortion (used in aurora.css)
  const updateCSS = () => {
    const el = canvasRef.current?.parentElement;
    if (el) {
      el.style.setProperty('--mouse-x', `${mouse.current.x * 100}%`);
      el.style.setProperty('--mouse-y', `${mouse.current.y * 100}%`);
    }
  };

  // Smooth interpolation of mouse position
  const lerp = (a, b, f) => a + (b - a) * f;

  const onPointerMove = (e) => {
    const rect = canvasRef.current?.parentElement?.getBoundingClientRect();
    if (!rect) return;
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;
    target.current = { x, y };
  };

  useEffect(() => {
      const y = ((clientY - rect.top) / rect.height) * 100;
      el.style.setProperty('--mouse-x', `${x}%`);
      el.style.setProperty('--mouse-y', `${y}%`);
    };
    el.addEventListener('pointermove', handleMove);
    return () => el.removeEventListener('pointermove', handleMove);
  }, []);

  return (
    <div className="aurora-bg" ref={containerRef}>
      {children}
      <div className="glow-blobs" aria-hidden="true"></div>
    </div>
  );
};

export default AuroraBackground;
