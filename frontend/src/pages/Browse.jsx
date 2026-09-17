import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Compass, Filter, Loader2, X } from 'lucide-react';
import MovieGrid from '../components/MovieGrid';
import EmptyState from '../components/EmptyState';
import { useBrowse, useGenres } from '../lib/queries';

const SORTS = [
  { value: 'popularity', label: 'Most popular' },
  { value: 'rating', label: 'Highest rated' },
  { value: 'trending', label: 'Trending now' },
  { value: 'release_date', label: 'Newest first' },
  { value: 'votes', label: 'Most rated' },
  { value: 'title', label: 'A-Z' },
];

const CURRENT_YEAR = new Date().getFullYear();

const DECADES = [
  { label: `${CURRENT_YEAR - 2}+`, from: CURRENT_YEAR - 2, to: null },
  { label: '2020s', from: 2020, to: 2029 },
  { label: '2010s', from: 2010, to: 2019 },
  { label: '2000s', from: 2000, to: 2009 },
  { label: '90s', from: 1990, to: 1999 },
  { label: '80s', from: 1980, to: 1989 },
  { label: 'Pre-1980', from: null, to: 1979 },
];

const RATING_FLOORS = [
  { label: 'Any rating', value: '' },
  { label: '3.5+', value: '3.5' },
  { label: '4.0+', value: '4' },
  { label: '4.3+', value: '4.3' },
];

export default function Browse({ publicMode = false }) {
  // Filters live in the URL so a filtered view is shareable and survives reload.
  const [searchParams, setSearchParams] = useSearchParams();
  const [showFilters, setShowFilters] = useState(false);

  const filters = useMemo(
    () => ({
      sort_by: searchParams.get('sort') || 'popularity',
      order: searchParams.get('sort') === 'title' ? 'asc' : 'desc',
      genre: searchParams.get('genre') || undefined,
      year_from: searchParams.get('from') || undefined,
      year_to: searchParams.get('to') || undefined,
      min_rating: searchParams.get('min') || undefined,
      page_size: 36,
    }),
    [searchParams],
  );

  const { data: genreData } = useGenres();
  const { data, isLoading, isFetchingNextPage, hasNextPage, fetchNextPage } = useBrowse(filters);

  const movies = useMemo(
    () => (data?.pages ?? []).flatMap((page) => page.items ?? []),
    [data],
  );
  const total = data?.pages?.[0]?.pagination?.total_items ?? 0;

  const update = useCallback(
    (patch) => {
      const next = new URLSearchParams(searchParams);
      Object.entries(patch).forEach(([key, value]) => {
        if (value === null || value === undefined || value === '') next.delete(key);
        else next.set(key, String(value));
      });
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const activeCount = ['genre', 'from', 'to', 'min'].filter((key) => searchParams.get(key)).length;

  // Infinite scroll via a sentinel below the grid. An IntersectionObserver costs
  // nothing while idle, unlike a scroll listener that fires on every frame.
  const sentinel = useRef(null);
  useEffect(() => {
    const node = sentinel.current;
    if (!node || !hasNextPage) return undefined;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !isFetchingNextPage) fetchNextPage();
      },
      // Start fetching before the sentinel is visible so the next rows are usually
      // already there by the time the user reaches them.
      { rootMargin: '900px 0px' },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  const activeDecade = DECADES.find(
    (decade) =>
      String(decade.from ?? '') === (searchParams.get('from') ?? '') &&
      String(decade.to ?? '') === (searchParams.get('to') ?? ''),
  );

  return (
    <div className="mx-auto max-w-[1500px] px-5 py-8 sm:px-6">
      <header className="mb-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold tracking-tightest text-white">
              {publicMode ? 'Discover' : 'Browse'}
            </h1>
            <p className="mt-1.5 text-sm text-white/45">
              {total > 0 ? `${total.toLocaleString()} films` : 'Loading catalogue…'}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <select
              value={filters.sort_by}
              onChange={(event) => update({ sort: event.target.value })}
              aria-label="Sort by"
              className="rounded-full border border-white/[0.09] bg-ink-900 px-4 py-2 text-sm text-white/80 focus:border-violet-600/70 focus:outline-none"
            >
              {SORTS.map(({ value, label }) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>

            <button
              type="button"
              onClick={() => setShowFilters((open) => !open)}
              className={`btn-secondary px-4 py-2 text-sm ${showFilters ? 'border-white/25' : ''}`}
              aria-expanded={showFilters}
            >
              <Filter className="h-4 w-4" />
              Filters
              {activeCount > 0 && (
                <span className="ml-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-violet-600 px-1 text-2xs font-bold text-white">
                  {activeCount}
                </span>
              )}
            </button>
          </div>
        </div>

        {showFilters && (
          <div className="mt-5 space-y-5 rounded-2xl border border-white/[0.07] bg-ink-900/50 p-5">
            <div>
              <span className="mb-2 block text-2xs font-medium text-white/60">Genre</span>
              <div className="flex flex-wrap gap-1.5">
                <button
                  type="button"
                  onClick={() => update({ genre: null })}
                  className={`chip ${!searchParams.get('genre') ? 'chip-active' : ''}`}
                >
                  All
                </button>
                {(genreData?.genres ?? []).map(({ name, movie_count }) => (
                  <button
                    key={name}
                    type="button"
                    onClick={() =>
                      update({ genre: searchParams.get('genre') === name ? null : name })
                    }
                    className={`chip ${searchParams.get('genre') === name ? 'chip-active' : ''}`}
                  >
                    {name}
                    <span className="tabular-nums text-white/30">{movie_count}</span>
                  </button>
                ))}
              </div>
            </div>

            <div>
              <span className="mb-2 block text-2xs font-medium text-white/60">Era</span>
              <div className="flex flex-wrap gap-1.5">
                <button
                  type="button"
                  onClick={() => update({ from: null, to: null })}
                  className={`chip ${!activeDecade ? 'chip-active' : ''}`}
                >
                  Any
                </button>
                {DECADES.map((decade) => (
                  <button
                    key={decade.label}
                    type="button"
                    onClick={() =>
                      update(
                        activeDecade?.label === decade.label
                          ? { from: null, to: null }
                          : { from: decade.from, to: decade.to },
                      )
                    }
                    className={`chip ${activeDecade?.label === decade.label ? 'chip-active' : ''}`}
                  >
                    {decade.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <span className="mb-2 block text-2xs font-medium text-white/60">Minimum rating</span>
              <div className="flex flex-wrap gap-1.5">
                {RATING_FLOORS.map(({ label, value }) => (
                  <button
                    key={label}
                    type="button"
                    onClick={() => update({ min: value || null })}
                    className={`chip ${(searchParams.get('min') ?? '') === value ? 'chip-active' : ''}`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {activeCount > 0 && (
              <button
                type="button"
                onClick={() => update({ genre: null, from: null, to: null, min: null })}
                className="btn-ghost text-2xs"
              >
                <X className="h-3 w-3" />
                Clear all filters
              </button>
            )}
          </div>
        )}
      </header>

      <MovieGrid
        movies={movies}
        loading={isLoading}
        skeletonCount={24}
        emptyState={
          <EmptyState
            icon={Compass}
            title="No films match those filters"
            description="Try clearing the era or rating floor — some combinations are very narrow."
          />
        }
      />

      <div ref={sentinel} className="h-4" aria-hidden="true" />

      {isFetchingNextPage && (
        <div className="flex justify-center py-8">
          <Loader2 className="h-5 w-5 animate-spin text-white/35" />
        </div>
      )}

      {!hasNextPage && movies.length > 0 && (
        <p className="py-10 text-center text-2xs text-white/25">
          That&apos;s all {total.toLocaleString()} films.
        </p>
      )}
    </div>
  );
}
