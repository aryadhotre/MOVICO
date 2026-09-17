import { useMemo } from 'react';
import { motion, useReducedMotion } from 'framer-motion';

/**
 * Genre affinity drawn as a radar polygon — a "taste fingerprint".
 *
 * A radar is the right form here and a bar chart is not: the question is the
 * *shape* of someone's taste, not the ranking of any single genre. A viewer
 * spread evenly across eight genres and one concentrated in two produce
 * immediately distinguishable silhouettes, which a bar list cannot convey at a
 * glance.
 *
 * Hand-drawn in SVG rather than pulled from a charting library: the geometry is
 * a few lines of trigonometry, and a chart runtime would cost more bundle than
 * the entire page it sits on.
 *
 * Axes are capped at eight. Beyond that the polygon degenerates into a circle and
 * the labels collide.
 */
const SIZE = 260;
const CENTRE = SIZE / 2;
const RADIUS = SIZE * 0.34;
const RINGS = 4;

function pointAt(index, count, magnitude) {
  // Start at twelve o'clock and run clockwise, which is how a radar is read.
  const angle = (Math.PI * 2 * index) / count - Math.PI / 2;
  return [
    CENTRE + Math.cos(angle) * RADIUS * magnitude,
    CENTRE + Math.sin(angle) * RADIUS * magnitude,
  ];
}

export default function TasteFingerprint({ genres = [], className = '' }) {
  const reduce = useReducedMotion();

  const axes = useMemo(() => genres.slice(0, 8), [genres]);

  const { polygon, ringPaths, spokes, labels } = useMemo(() => {
    const count = axes.length;
    if (count < 3) return { polygon: '', ringPaths: [], spokes: [], labels: [] };

    const peak = Math.max(...axes.map((axis) => axis.movie_count), 1);

    const shape = axes
      .map((axis, index) => {
        // A floor of 0.12 keeps a near-zero genre visible as a dimple rather than
        // collapsing the polygon onto its own centre.
        const magnitude = Math.max(0.12, axis.movie_count / peak);
        return pointAt(index, count, magnitude).join(',');
      })
      .join(' ');

    const rings = Array.from({ length: RINGS }, (_, ring) => {
      const scale = (ring + 1) / RINGS;
      return axes.map((_, index) => pointAt(index, count, scale).join(',')).join(' ');
    });

    const lines = axes.map((_, index) => pointAt(index, count, 1));

    const text = axes.map((axis, index) => {
      const [x, y] = pointAt(index, count, 1.3);
      return {
        name: axis.name,
        count: axis.movie_count,
        x,
        y,
        // Anchor outward from the centre so labels never overlap the polygon.
        anchor: x > CENTRE + 6 ? 'start' : x < CENTRE - 6 ? 'end' : 'middle',
      };
    });

    return { polygon: shape, ringPaths: rings, spokes: lines, labels: text };
  }, [axes]);

  if (axes.length < 3) {
    return (
      <p className="py-10 text-center text-sm text-print-400">
        Rate films across at least three genres to see your fingerprint.
      </p>
    );
  }

  return (
    <div className={`flex justify-center ${className}`}>
      <svg
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        className="h-auto w-full max-w-[320px] overflow-visible"
        role="img"
        aria-label={`Genre affinity: ${axes.map((a) => `${a.name} ${a.movie_count}`).join(', ')}`}
      >
        {/* Graticule */}
        {ringPaths.map((ring, index) => (
          <polygon
            key={index}
            points={ring}
            fill="none"
            stroke="currentColor"
            strokeWidth="0.5"
            className="text-print-100/12"
          />
        ))}

        {spokes.map(([x, y], index) => (
          <line
            key={index}
            x1={CENTRE}
            y1={CENTRE}
            x2={x}
            y2={y}
            stroke="currentColor"
            strokeWidth="0.5"
            className="text-print-100/10"
          />
        ))}

        {/* The fingerprint itself, scaled up from the centre on first paint. */}
        <motion.polygon
          points={polygon}
          className="fill-tungsten-500/20 stroke-tungsten-500"
          strokeWidth="1.5"
          strokeLinejoin="round"
          initial={reduce ? false : { scale: 0, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
          style={{ transformOrigin: `${CENTRE}px ${CENTRE}px` }}
        />

        {polygon.split(' ').map((pair, index) => {
          const [x, y] = pair.split(',').map(Number);
          return (
            <motion.circle
              key={index}
              cx={x}
              cy={y}
              r="2.5"
              className="fill-tungsten-400"
              initial={reduce ? false : { opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.5 + index * 0.05, duration: 0.3 }}
            />
          );
        })}

        {labels.map((label) => (
          <g key={label.name}>
            <text
              x={label.x}
              y={label.y}
              textAnchor={label.anchor}
              dominantBaseline="middle"
              className="fill-print-200 font-mono text-[7px] uppercase tracking-wider"
            >
              {label.name}
            </text>
            <text
              x={label.x}
              y={label.y + 9}
              textAnchor={label.anchor}
              dominantBaseline="middle"
              className="fill-print-500 font-mono text-[7px] tabular-nums"
            >
              {label.count}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}
