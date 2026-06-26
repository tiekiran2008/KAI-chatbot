'use client';

import { useState, useEffect, useRef } from 'react';
import { Palette } from 'lucide-react';

const PRESET_COLORS = [
  { label: 'Red',     value: '#ff3b30' },
  { label: 'Purple',  value: '#8b5cf6' },
  { label: 'Blue',    value: '#3b82f6' },
  { label: 'Cyan',    value: '#06b6d4' },
  { label: 'Pink',    value: '#ec4899' },
  { label: 'Rose',    value: '#f43f5e' },
  { label: 'Emerald', value: '#10b981' },
  { label: 'Amber',   value: '#f59e0b' },
];

function hexToRgb(hex) {
  const cleaned = hex.replace('#', '');
  const bigint = parseInt(cleaned, 16);
  const r = (bigint >> 16) & 255;
  const g = (bigint >> 8) & 255;
  const b = bigint & 255;
  return { r, g, b };
}

function hexToHsl(hex) {
  let cleaned = hex.replace('#', '');
  if (cleaned.length === 3) {
    cleaned = cleaned.split('').map(c => c + c).join('');
  }
  const r = parseInt(cleaned.substring(0, 2), 16) / 255;
  const g = parseInt(cleaned.substring(2, 4), 16) / 255;
  const b = parseInt(cleaned.substring(4, 6), 16) / 255;

  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  let h, s, l = (max + min) / 2;

  if (max === min) {
    h = s = 0; // achromatic
  } else {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r: h = (g - b) / d + (g < b ? 6 : 0); break;
      case g: h = (b - r) / d + 2; break;
      case b: h = (r - g) / d + 4; break;
    }
    h /= 6;
  }

  return `${Math.round(h * 360)} ${Math.round(s * 100)}% ${Math.round(l * 100)}%`;
}

// Glow orb — a blurred, colored circle that smoothly transitions its color
function GlowOrb({ color, style }) {
  return (
    <div
      aria-hidden="true"
      style={{
        position: 'fixed',
        pointerEvents: 'none',
        zIndex: 0,
        borderRadius: '50%',
        backgroundColor: color,
        filter: 'blur(90px)',
        opacity: 0.12,
        transition: 'background-color 0.7s cubic-bezier(0.4, 0, 0.2, 1)',
        ...style,
      }}
    />
  );
}

export default function GlowColorPicker() {
  const [color, setColor] = useState('#8b5cf6');
  const [open, setOpen] = useState(false);
  const panelRef = useRef(null);

  const updateCssVariables = (hexColor) => {
    const hslValue = hexToHsl(hexColor);
    document.documentElement.style.setProperty('--primary', hslValue);
  };

  // Restore saved color from localStorage on first mount
  useEffect(() => {
    const saved = localStorage.getItem('kai-glow-color');
    if (saved) {
      setColor(saved);
      updateCssVariables(saved);
    } else {
      updateCssVariables('#8b5cf6'); // Default theme
    }
  }, []);

  const applyColor = (newColor) => {
    setColor(newColor);
    localStorage.setItem('kai-glow-color', newColor);
    updateCssVariables(newColor);
  };

  // Close panel when clicking outside
  useEffect(() => {
    if (!open) return;
    const handleClickOutside = (e) => {
      if (panelRef.current && !panelRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open]);

  const { r, g, b } = hexToRgb(color);
  const rgbStr = `${r}, ${g}, ${b}`;

  return (
    <>
      {/* ── Animated background glow orbs ── */}
      <GlowOrb color={color} style={{ width: 600, height: 600, top: '10%',  left: '-10%' }} />
      <GlowOrb color={color} style={{ width: 500, height: 500, bottom: '5%', right: '-8%', opacity: 0.09 }} />

      {/* ── Floating button + picker panel ── */}
      <div ref={panelRef} className="fixed bottom-5 right-5 z-50 flex flex-col items-end gap-2">

        {/* Picker panel */}
        {open && (
          <div
            className="mb-1 p-4 rounded-2xl shadow-2xl flex flex-col gap-4"
            style={{
              background: 'rgba(12, 12, 18, 0.88)',
              border: `1px solid rgba(${rgbStr}, 0.25)`,
              backdropFilter: 'blur(24px)',
              WebkitBackdropFilter: 'blur(24px)',
              boxShadow: `0 8px 40px rgba(${rgbStr}, 0.2), 0 2px 8px rgba(0,0,0,0.5)`,
              animation: 'glowPickerFadeIn 0.22s cubic-bezier(0.16, 1, 0.3, 1) both',
            }}
          >
            <p className="text-[10px] font-bold text-white/30 uppercase tracking-[0.15em] select-none">
              Glow Color
            </p>

            {/* Preset swatches */}
            <div className="flex gap-2 flex-wrap">
              {PRESET_COLORS.map((c) => (
                <button
                  key={c.value}
                  title={c.label}
                  onClick={() => applyColor(c.value)}
                  className="w-7 h-7 rounded-full focus:outline-none"
                  style={{
                    background: c.value,
                    boxShadow: color === c.value
                      ? `0 0 0 2px #0c0c12, 0 0 0 4px ${c.value}, 0 0 14px ${c.value}`
                      : '0 0 0 1px rgba(255,255,255,0.12)',
                    transform: color === c.value ? 'scale(1.18)' : 'scale(1)',
                    transition: 'transform 0.25s ease, box-shadow 0.25s ease',
                  }}
                />
              ))}
            </div>

            {/* Divider */}
            <div style={{ height: 1, background: `rgba(${rgbStr}, 0.15)` }} />

            {/* Custom color row */}
            <div className="flex items-center gap-3">
              <label className="text-[11px] text-white/30 font-medium select-none">Custom</label>
              <input
                type="color"
                value={color}
                onChange={(e) => applyColor(e.target.value)}
                className="w-8 h-8 rounded-lg cursor-pointer"
                style={{
                  border: `1px solid rgba(${rgbStr}, 0.3)`,
                  padding: '2px',
                  background: 'transparent',
                }}
              />
              <span
                className="text-[11px] font-mono px-2 py-0.5 rounded"
                style={{
                  color: color,
                  background: `rgba(${rgbStr}, 0.12)`,
                  transition: 'color 0.5s ease, background 0.5s ease',
                }}
              >
                {color}
              </span>
            </div>
          </div>
        )}

        {/* Toggle button */}
        <button
          onClick={() => setOpen((o) => !o)}
          title="Change glow color"
          className="w-11 h-11 rounded-full flex items-center justify-center hover:scale-105 active:scale-95"
          style={{
            background: `rgba(${rgbStr}, 0.22)`,
            backdropFilter: 'blur(14px)',
            WebkitBackdropFilter: 'blur(14px)',
            boxShadow: `0 0 24px rgba(${rgbStr}, 0.45), 0 4px 14px rgba(0,0,0,0.45)`,
            border: `1px solid rgba(${rgbStr}, 0.45)`,
            transition: 'background 0.5s ease, box-shadow 0.5s ease, border-color 0.5s ease',
          }}
        >
          <Palette size={17} color={color} style={{ transition: 'color 0.5s ease' }} />
        </button>
      </div>

      {/* Keyframes */}
      <style>{`
        @keyframes glowPickerFadeIn {
          from { opacity: 0; transform: translateY(12px) scale(0.96); }
          to   { opacity: 1; transform: translateY(0)   scale(1); }
        }
      `}</style>
    </>
  );
}
