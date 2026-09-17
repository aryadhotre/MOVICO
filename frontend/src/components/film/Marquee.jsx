import { useMemo } from 'react';
import { useReducedMotion } from 'framer-motion';

/**
 * An endlessly travelling text band, like a cinema marquee.
 *
 * The content is duplicated and the track translated by exactly -50%, which is
 * what makes the loop seamless without any JavaScript running per frame — the
 * whole thing is one compositor-driven `transform`.
 */
export default function Marquee({ items = [], speed = 42, separator = '✦', className = '' }) {
  const reduce = useReducedMotion();
  const track = useMemo(() => [...items, ...items], [items]);

  if (items.length === 0) return null;

  return (
    <div
      aria-hidden="true"
      className={`relative flex overflow-hidden border-y border-print-100/10 py-3 ${className}`}
    >
      <div
        className="flex w-max shrink-0 items-center gap-8 pr-8"
        style={reduce ? undefined : { animation: `marquee-travel ${speed}s linear infinite` }}
      >
        {track.map((item, index) => (
          <span key={index} className="flex items-center gap-8 whitespace-nowrap">
            <span className="font-display text-sm uppercase tracking-marquee text-print-300">
              {item}
            </span>
            <span className="text-tungsten-500/60">{separator}</span>
          </span>
        ))}
      </div>

      <style>{`
        @keyframes marquee-travel {
          from { transform: translateX(0); }
          to   { transform: translateX(-50%); }
        }
      `}</style>
    </div>
  );
}
