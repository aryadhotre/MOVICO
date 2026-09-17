/**
 * The MOVICO mark: a projector gate seen head-on.
 *
 * The outer square is the gate aperture, the inner circle the lens, and the four
 * notches the registration pins that hold each frame steady while it is exposed.
 * Drawn flat and monoline rather than as a gradient badge — cinema identities
 * (Criterion's C, MUBI's wordmark, A24) are almost all flat marks, and a
 * gradient-filled rounded square is the single most recognisable tell of a
 * generated logo.
 */
export default function Logo({ className = '', showWordmark = true, size = 28 }) {
  return (
    <span className={`inline-flex items-center gap-3 ${className}`}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 32 32"
        fill="none"
        aria-hidden="true"
        className="shrink-0 text-tungsten-500"
      >
        <rect x="1.5" y="1.5" width="29" height="29" stroke="currentColor" strokeWidth="1.6" />
        <circle cx="16" cy="16" r="8.5" stroke="currentColor" strokeWidth="1.6" />
        <circle cx="16" cy="16" r="3" fill="currentColor" />
        {/* Registration pins, one per edge. */}
        <path d="M16 1.5v4M16 26.5v4M1.5 16h4M26.5 16h4" stroke="currentColor" strokeWidth="1.6" />
      </svg>

      {showWordmark && (
        <span className="font-display text-base font-medium uppercase tracking-marquee text-print-50">
          Movico
        </span>
      )}
    </span>
  );
}
