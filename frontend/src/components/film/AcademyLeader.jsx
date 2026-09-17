import { useEffect, useState } from 'react';

/**
 * An Academy countdown leader, used as the loading state.
 *
 * The real thing was standardised by the Academy in 1930 and spliced to the head
 * of every release print: a number per foot of film, a rotating sweep hand, and
 * crosshairs for framing the gate. This reproduces it as SVG.
 *
 * Two details from the original are kept because they are the whole reason it
 * looks authentic rather than like a generic circular spinner:
 *
 * * the sweep hand completes exactly one revolution per number, which is what
 *   made it a usable timing reference for a projectionist;
 * * the count runs *down*, and stops rather than looping past the end.
 *
 * (The original spells "NINE" and "SIX" as words so they cannot be misread when
 * the frame is upside down. At this size digits are clearer, so it counts 8 -> 3.)
 */
export default function AcademyLeader({ size = 132, label = 'Loading' }) {
  const [count, setCount] = useState(8);

  useEffect(() => {
    const timer = setInterval(() => {
      setCount((current) => (current <= 3 ? 8 : current - 1));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div
      className="relative inline-flex items-center justify-center"
      style={{ width: size, height: size }}
      role="status"
      aria-live="polite"
    >
      <svg viewBox="0 0 100 100" className="absolute inset-0 h-full w-full">
        <circle cx="50" cy="50" r="48" fill="none" stroke="currentColor" strokeWidth="0.6" className="text-print-100/25" />
        <circle cx="50" cy="50" r="38" fill="none" stroke="currentColor" strokeWidth="0.6" className="text-print-100/15" />
        <circle cx="50" cy="50" r="27" fill="none" stroke="currentColor" strokeWidth="0.6" className="text-print-100/10" />

        {/* Framing crosshairs, extending past the outer ring as on the real leader. */}
        <line x1="50" y1="0" x2="50" y2="100" stroke="currentColor" strokeWidth="0.5" className="text-print-100/20" />
        <line x1="0" y1="50" x2="100" y2="50" stroke="currentColor" strokeWidth="0.5" className="text-print-100/20" />

        {/* The sweep hand: one full turn per second, matching one number. */}
        <g className="origin-center animate-leader-sweep">
          <path d="M50 50 L50 4" stroke="currentColor" strokeWidth="1.6" className="text-tungsten-500" strokeLinecap="round" />
          <path d="M50 50 L50 4 A46 46 0 0 1 78 14 Z" className="fill-tungsten-500/12" />
        </g>

        <circle cx="50" cy="50" r="2" className="fill-tungsten-500" />
      </svg>

      <span
        className="relative font-display text-5xl font-medium tabular-nums text-print-50"
        style={{ fontSize: size * 0.34 }}
      >
        {count}
      </span>

      <span className="sr-only">{label}</span>
    </div>
  );
}
