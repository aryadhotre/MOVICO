import MovieCard from './MovieCard';

function GridSkeleton({ count }) {
  return Array.from({ length: count }, (_, index) => (
    <div key={`skeleton-${index}`}>
      <div className="skeleton aspect-[2/3] w-full" />
      <div className="skeleton mt-2 h-3 w-4/5" />
    </div>
  ));
}

/**
 * Responsive poster grid.
 *
 * `auto-fill` with a minimum track keeps the column count tied to the available
 * width rather than to a set of breakpoints, so the grid stays dense at any window
 * size without a cascade of media queries.
 */
export default function MovieGrid({
  movies = [],
  loading = false,
  skeletonCount = 18,
  showMatch = false,
  numbered = false,
  emptyState = null,
  priorityCount = 6,
  dense = false,
}) {
  if (!loading && movies.length === 0) return emptyState;

  // Dense packs more titles per row for scanning a long catalogue; comfortable
  // gives the artwork room. Both are driven by the track minimum rather than a
  // fixed column count, so neither breaks at an awkward viewport width.
  const track = dense
    ? 'repeat(auto-fill, minmax(clamp(96px, 10vw, 132px), 1fr))'
    : 'repeat(auto-fill, minmax(clamp(130px, 15vw, 180px), 1fr))';

  return (
    <div
      className={dense ? 'grid gap-x-3 gap-y-5' : 'grid gap-x-4 gap-y-6'}
      style={{ gridTemplateColumns: track }}
    >
      {movies.map((movie, index) => (
        <MovieCard
          key={movie.id}
          movie={movie}
          rank={numbered ? index + 1 : null}
          matchScore={showMatch ? movie.matchScore ?? null : null}
          priority={index < priorityCount}
          showRating={!dense}
        />
      ))}
      {loading && <GridSkeleton count={skeletonCount} />}
    </div>
  );
}
