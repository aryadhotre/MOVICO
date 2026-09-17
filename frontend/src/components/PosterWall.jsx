import { useMemo } from 'react';
import { posterUrl } from '../lib/images';

/**
 * The drifting poster mosaic behind the landing hero.
 *
 * Built from real catalogue artwork rather than stock imagery, so the page is
 * showing the actual product. Performance constraints that shape it:
 *
 * * `w185` posters only — this is a background at maybe 130px wide, and pulling
 *   `w500` for decoration would compete with the content for bandwidth.
 * * Columns animate with a single CSS `transform` translation, which the compositor
 *   handles off the main thread. Animating `top` or `background-position` here
 *   would repaint continuously behind everything else.
 * * Each column's list is duplicated so the translation can loop seamlessly
 *   without a JavaScript scroll handler.
 * * `aria-hidden`, because it carries no information a screen reader needs.
 */
export default function PosterWall({ movies = [], columns = 7 }) {
  const lanes = useMemo(() => {
    const usable = movies.filter((movie) => movie.poster_path);
    if (usable.length === 0) return [];

    const result = Array.from({ length: columns }, () => []);
    // Deal round-robin so adjacent columns never show the same title.
    usable.forEach((movie, index) => {
      result[index % columns].push(movie);
    });
    // Every lane needs enough tiles to fill a tall viewport twice over.
    return result.map((lane) => {
      const filled = [...lane];
      while (filled.length < 6 && lane.length > 0) filled.push(...lane);
      return [...filled, ...filled];
    });
  }, [movies, columns]);

  if (lanes.length === 0) return null;

  return (
    <div className="absolute inset-0 overflow-hidden" aria-hidden="true">
      <div className="absolute inset-0 flex justify-center gap-3 px-3 opacity-[0.28]">
        {lanes.map((lane, laneIndex) => (
          <div
            key={laneIndex}
            className="flex w-[13vw] min-w-[110px] shrink-0 flex-col gap-3"
            style={{
              // Alternating directions and varied durations stop the wall from
              // reading as one sliding block.
              animation: `poster-drift-${laneIndex % 2 === 0 ? 'up' : 'down'} ${
                58 + laneIndex * 7
              }s linear infinite`,
              transform: `translateY(${laneIndex % 2 === 0 ? '0' : '-28%'})`,
            }}
          >
            {lane.map((movie, index) => (
              <img
                key={`${movie.id}-${index}`}
                src={posterUrl(movie.poster_path, 185)}
                alt=""
                loading={laneIndex < 4 && index < 3 ? 'eager' : 'lazy'}
                decoding="async"
                className="aspect-[2/3] w-full rounded-lg object-cover shadow-card"
              />
            ))}
          </div>
        ))}
      </div>

      {/* Vignette that fades the wall into the page so it never fights the copy. */}
      <div className="absolute inset-0 bg-gradient-to-b from-ink-950/70 via-ink-950/88 to-ink-950" />
      <div className="absolute inset-0 bg-[radial-gradient(60rem_40rem_at_50%_38%,transparent,rgba(6,6,10,0.94))]" />

      <style>{`
        @keyframes poster-drift-up {
          from { transform: translateY(0); }
          to   { transform: translateY(-50%); }
        }
        @keyframes poster-drift-down {
          from { transform: translateY(-50%); }
          to   { transform: translateY(0); }
        }
        @media (prefers-reduced-motion: reduce) {
          [style*="poster-drift"] { animation: none !important; }
        }
      `}</style>
    </div>
  );
}
