/**
 * A strip of 35mm sprocket holes.
 *
 * Drawn as an SVG pattern of rounded rectangles rather than a repeating linear
 * gradient. A gradient can only produce solid bands, which read as grey dashes
 * painted on the strip — the whole point of a perforation is that it is a *hole*,
 * so it has to be a light shape inset in a darker band with a little corner
 * radius, which is what Kodak Standard (KS-1870) perfs actually look like.
 *
 * Proportions follow real stock: the hole is wider than it is tall on the
 * horizontal run, with roughly its own width of film between each one.
 */
export default function Perforations({ orientation = 'horizontal', className = '' }) {
  const horizontal = orientation === 'horizontal';
  const id = `perf-${orientation}`;

  return (
    <div
      aria-hidden="true"
      className={`relative overflow-hidden bg-film-950 ${
        horizontal ? 'h-[18px] w-full' : 'h-full w-[18px]'
      } ${className}`}
    >
      <svg className="absolute inset-0 h-full w-full" aria-hidden="true">
        <defs>
          <pattern
            id={id}
            width={horizontal ? 26 : 18}
            height={horizontal ? 18 : 26}
            patternUnits="userSpaceOnUse"
          >
            <rect
              x={horizontal ? 5 : 4}
              y={horizontal ? 4 : 5}
              width={horizontal ? 16 : 10}
              height={horizontal ? 10 : 16}
              rx="2.5"
              className="fill-print-100/[0.13]"
            />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill={`url(#${id})`} />
      </svg>

      {/* Edge lines where the strip meets the frame. */}
      <div
        className={`absolute ${horizontal ? 'inset-x-0 top-0 h-px' : 'inset-y-0 left-0 w-px'} bg-print-100/10`}
      />
      <div
        className={`absolute ${horizontal ? 'inset-x-0 bottom-0 h-px' : 'inset-y-0 right-0 w-px'} bg-print-100/10`}
      />
    </div>
  );
}
