import { useEffect, useRef } from 'react';
import '@/styles/aurora.css';

/**
 * AuroraBackground renders a full-screen canvas with an animated aurora effect.
 * It also tracks mouse position and updates CSS custom properties --mouse-x / --mouse-y
 * so the aurora.css radial-gradient overlay reacts to cursor movement.
 */
export default function AuroraBackground() {
  const canvasRef = useRef(null);
  const mouse = useRef({ x: 0.5, y: 0.5 }); // normalized 0-1

  // Write mouse position as CSS custom properties on the parent element
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
        ctx.arc(
          canvas.width / 2 + offsetX,
          canvas.height / 2 + offsetY,
          canvas.width * 0.7,
          0,
          Math.PI * 2
        );
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
    <canvas
      ref={canvasRef}
      className="absolute inset-0 w-full h-full pointer-events-none"
      aria-hidden="true"
    />
  );
}
