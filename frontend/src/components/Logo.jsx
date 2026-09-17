/**
 * The MOVICO mark.
 *
 * An aperture-style glyph: three blades around a lens, which reads as both a
 * camera iris and a play triangle. Drawn as inline SVG with `currentColor` and a
 * gradient so it stays crisp at any size and needs no image request.
 */
export default function Logo({ className = '', showWordmark = true, size = 30 }) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 32 32"
        fill="none"
        aria-hidden="true"
        className="shrink-0"
      >
        <defs>
          <linearGradient id="movico-mark" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
            <stop stopColor="#8B6DFF" />
            <stop offset="0.55" stopColor="#A855F7" />
            <stop offset="1" stopColor="#FF4D8D" />
          </linearGradient>
        </defs>

        <rect x="0.9" y="0.9" width="30.2" height="30.2" rx="9.2" fill="url(#movico-mark)" />
        <rect
          x="0.9"
          y="0.9"
          width="30.2"
          height="30.2"
          rx="9.2"
          stroke="white"
          strokeOpacity="0.22"
          strokeWidth="1.1"
        />

        {/* Aperture blades */}
        <path
          d="M16 6.6a9.4 9.4 0 0 1 8.14 4.7H16.9L12.4 7.5A9.35 9.35 0 0 1 16 6.6Z"
          fill="white"
          fillOpacity="0.95"
        />
        <path
          d="M6.9 19.1a9.4 9.4 0 0 1 1.5-9.3l3.6 6.25-2.2 5.3a9.36 9.36 0 0 1-2.9-2.25Z"
          fill="white"
          fillOpacity="0.78"
        />
        <path
          d="M19.6 24.9a9.4 9.4 0 0 1-9.26-1.6l6.45.02 3.65-6.33a9.36 9.36 0 0 1-.84 7.91Z"
          fill="white"
          fillOpacity="0.88"
        />
        <circle cx="16" cy="16" r="2.55" fill="white" />
      </svg>

      {showWordmark && (
        <span className="text-[1.0625rem] font-bold tracking-[0.14em] text-white">
          MOVICO
        </span>
      )}
    </span>
  );
}
