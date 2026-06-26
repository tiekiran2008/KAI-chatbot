import { useRef, useState } from 'react';
import { motion } from 'framer-motion';
import '@/styles/magneticButton.css';

/**
 * MagneticButton
 * A button that subtly moves towards the cursor, creating a magnetic attraction effect.
 * It uses Framer Motion for smooth animation and vanilla calculations for the offset.
 *
 * Props:
 * - children: button label or inner content
 * - className: additional CSS classes
 * - ...props: any other button props (onClick, type, etc.)
 */
export default function MagneticButton({ children, className = '', ...props }) {
  const btnRef = useRef(null);
  const [offset, setOffset] = useState({ x: 0, y: 0 });

  // Calculate offset based on mouse position relative to button center
  const handleMouseMove = (e) => {
    const rect = btnRef.current?.getBoundingClientRect();
    if (!rect) return;
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const deltaX = e.clientX - cx;
    const deltaY = e.clientY - cy;
    // Scale the movement – smaller factor for subtle effect
    const factor = 0.15; // adjust for strength
    setOffset({
      x: deltaX * factor,
      y: deltaY * factor,
    });
  };

  const handleMouseLeave = () => {
    setOffset({ x: 0, y: 0 });
  };

  return (
    <motion.button
      ref={btnRef}
      className={`magnetic-button ${className}`}
      style={{
        transform: `translate(${offset.x}px, ${offset.y}px)`,
      }}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      whileHover={{ scale: 1.04 }}
      whileTap={{ scale: 0.96 }}
      {...props}
    >
      {children}
    </motion.button>
  );
}
