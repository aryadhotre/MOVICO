import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Loader2, Star, Trash2 } from 'lucide-react';
import Poster from '../components/Poster';
import RatingStars from '../components/RatingStars';
import EmptyState from '../components/EmptyState';
import { useToast } from '../components/Toast';
import { timecode } from '../lib/format';
import { useRateMovie, useRatingHistory, useRemoveRating } from '../lib/queries';

const FILTERS = [
  { label: 'All', test: () => true },
  { label: 'Loved 4.5+', test: (rating) => rating >= 4.5 },
  { label: 'Liked 3.5–4', test: (rating) => rating >= 3.5 && rating < 4.5 },
  { label: 'Mixed 3–3.5', test: (rating) => rating >= 3 && rating < 3.5 },
  { label: 'Disliked <3', test: (rating) => rating < 3 },
];

const SORTS = [
  { label: 'Recent', compare: null },
  { label: 'Highest', compare: (a, b) => b.rating - a.rating },
  { label: 'Lowest', compare: (a, b) => a.rating - b.rating },
  { label: 'A–Z', compare: (a, b) => a.movie.title.localeCompare(b.movie.title) },
];

export default function Ratings() {
  const { data, isLoading, hasNextPage, fetchNextPage, isFetchingNextPage } = useRatingHistory();
  const rate = useRateMovie();
  const removeRating = useRemoveRating();
  const toast = useToast();

  const [filterIndex, setFilterIndex] = useState(0);
  const [sortIndex, setSortIndex] = useState(0);

  const entries = useMemo(
    () => (data?.pages ?? []).flatMap((page) => page.items ?? []),
    [data],
  );
  const total = data?.pages?.[0]?.pagination?.total_items ?? 0;

  const visible = useMemo(() => {
    const filtered = entries.filter((entry) => FILTERS[filterIndex].test(entry.rating));
    const { compare } = SORTS[sortIndex];
    // The API already returns newest-first, so "Recent" is the unsorted order.
    return compare ? [...filtered].sort(compare) : filtered;
  }, [entries, filterIndex, sortIndex]);

  // Counts per band, so the filter chips say how much is behind each one.
  const bandCounts = useMemo(
    () => FILTERS.map((filter) => entries.filter((entry) => filter.test(entry.rating)).length),
    [entries],
  );

  const sentinel = useRef(null);
  useEffect(() => {
    const node = sentinel.current;
    if (!node || !hasNextPage) return undefined;
    const observer = new IntersectionObserver(
      (items) => {
        if (items[0].isIntersecting && !isFetchingNextPage) fetchNextPage();
      },
      { rootMargin: '600px 0px' },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  if (!isLoading && total === 0) {
    return (
      <div className="mx-auto max-w-[1100px] px-5 py-8 sm:px-8">
        <h1 className="title-card mb-10 text-3xl text-print-50">Your ratings</h1>
        <EmptyState
          icon={Star}
          title="You haven't rated anything yet"
          description="Ratings are the only thing the model learns from — ten is enough to get started."
          action={{ to: '/onboarding', label: 'Rate some films' }}
        />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1100px] px-5 py-8 sm:px-8">
      <header className="mb-8">
        <p className="slate-label mb-3">The log</p>
        <h1 className="title-card text-3xl text-print-50">Your ratings</h1>
        <p className="tech mt-3 normal-case">
          {total} film{total === 1 ? '' : 's'} rated
        </p>

        <div className="mt-6 flex flex-wrap items-center gap-4">
          <div className="flex flex-wrap gap-1.5">
            {FILTERS.map(({ label }, index) => (
              <button
                key={label}
                type="button"
                onClick={() => setFilterIndex(index)}
                className={`chip ${filterIndex === index ? 'chip-active' : ''}`}
              >
                {label}
                {bandCounts[index] > 0 && (
                  <span className="tabular-nums text-print-500">{bandCounts[index]}</span>
                )}
              </button>
            ))}
          </div>

          <div className="ml-auto flex items-center gap-2">
            <span className="tech">Sort</span>
            <select
              value={sortIndex}
              onChange={(event) => setSortIndex(Number(event.target.value))}
              aria-label="Sort ratings"
              className="border border-print-100/15 bg-film-900 px-3 py-2 font-mono text-2xs uppercase tracking-wider text-print-200 focus:border-tungsten-500 focus:outline-none"
            >
              {SORTS.map(({ label }, index) => (
                <option key={label} value={index}>{label}</option>
              ))}
            </select>
          </div>
        </div>
      </header>

      <ul className="divide-y divide-print-100/[0.07] border-y border-print-100/[0.07]">
        {isLoading
          ? Array.from({ length: 8 }, (_, index) => (
              <li key={index} className="flex items-center gap-4 py-3">
                <div className="skeleton h-[84px] w-14 shrink-0" />
                <div className="flex-1 space-y-2">
                  <div className="skeleton h-3.5 w-1/3" />
                  <div className="skeleton h-3 w-1/5" />
                </div>
              </li>
            ))
          : visible.map(({ movie, rating, rated_at: ratedAt }) => (
              <li key={movie.id} className="group relative flex items-center gap-4 py-3">
                {/* Rating strength as a rule down the left edge, so the list can be
                    scanned for highs and lows without reading every star row. */}
                <span
                  aria-hidden="true"
                  className="absolute inset-y-2 left-0 w-[2px] bg-tungsten-500"
                  style={{ opacity: Math.max(0.15, rating / 5) }}
                />

                <Link to={`/movie/${movie.id}`} className="ml-3 w-14 shrink-0">
                  <Poster path={movie.poster_path} alt={movie.title} maxWidth={185} sizes="56px" />
                </Link>

                <div className="min-w-0 flex-1">
                  <Link
                    to={`/movie/${movie.id}`}
                    className="block truncate font-display text-sm uppercase tracking-slate text-print-100 transition-colors hover:text-tungsten-400"
                  >
                    {movie.title}
                  </Link>
                  <p className="mt-1 truncate font-mono text-2xs tabular-nums text-print-500">
                    {movie.year}
                    {movie.runtime > 0 && ` · ${timecode(movie.runtime)}`}
                    {movie.genres?.length > 0 && ` · ${movie.genres.slice(0, 2).join(', ')}`}
                  </p>
                  {ratedAt && (
                    <p className="mt-0.5 font-mono text-[10px] text-print-500/70">
                      Rated {new Date(ratedAt).toLocaleDateString()}
                    </p>
                  )}
                </div>

                <RatingStars
                  value={rating}
                  size={17}
                  onChange={(next) => {
                    if (next) {
                      rate.mutate({ movieId: movie.id, rating: next });
                      toast.push({ kind: 'rating', message: `Rated ${next.toFixed(1)}`, detail: movie.title });
                    } else {
                      removeRating.mutate(movie.id);
                      toast.push({ message: 'Rating removed', detail: movie.title });
                    }
                  }}
                />

                <button
                  type="button"
                  onClick={() => {
                    removeRating.mutate(movie.id);
                    toast.push({ message: 'Rating removed', detail: movie.title });
                  }}
                  aria-label={`Remove your rating of ${movie.title}`}
                  className="btn-ghost h-8 w-8 p-0 opacity-0 transition-opacity focus-visible:opacity-100 group-hover:opacity-100"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </li>
            ))}
      </ul>

      {!isLoading && visible.length === 0 && (
        <p className="tech py-20 text-center normal-case">Nothing in this band yet.</p>
      )}

      <div ref={sentinel} className="h-4" aria-hidden="true" />
      {isFetchingNextPage && (
        <div className="flex justify-center py-8">
          <Loader2 className="h-5 w-5 animate-spin text-tungsten-500" />
        </div>
      )}
    </div>
  );
}
