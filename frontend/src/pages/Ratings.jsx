import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Loader2, Star, Trash2 } from 'lucide-react';
import Poster from '../components/Poster';
import RatingStars from '../components/RatingStars';
import EmptyState from '../components/EmptyState';
import { useRateMovie, useRatingHistory, useRemoveRating } from '../lib/queries';

const FILTERS = [
  { label: 'All', test: () => true },
  { label: 'Loved (4.5+)', test: (rating) => rating >= 4.5 },
  { label: 'Liked (3.5-4)', test: (rating) => rating >= 3.5 && rating < 4.5 },
  { label: 'Didn’t like (<3)', test: (rating) => rating < 3 },
];

export default function Ratings() {
  const { data, isLoading, hasNextPage, fetchNextPage, isFetchingNextPage } = useRatingHistory();
  const rate = useRateMovie();
  const removeRating = useRemoveRating();
  const [filterIndex, setFilterIndex] = useState(0);

  const entries = useMemo(
    () => (data?.pages ?? []).flatMap((page) => page.items ?? []),
    [data],
  );
  const total = data?.pages?.[0]?.pagination?.total_items ?? 0;

  const visible = useMemo(
    () => entries.filter((entry) => FILTERS[filterIndex].test(entry.rating)),
    [entries, filterIndex],
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
      <div className="mx-auto max-w-[1500px] px-5 py-8 sm:px-6">
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
    <div className="mx-auto max-w-[1500px] px-5 py-8 sm:px-6">
      <header className="mb-6">
        <p className="slate-label mb-3">The log</p>
        <h1 className="title-card text-3xl text-print-50">Your ratings</h1>
        <p className="tech mt-3 normal-case">
          {total} film{total === 1 ? '' : 's'} rated
        </p>

        <div className="mt-5 flex flex-wrap gap-1.5">
          {FILTERS.map(({ label }, index) => (
            <button
              key={label}
              type="button"
              onClick={() => setFilterIndex(index)}
              className={`chip ${filterIndex === index ? 'chip-active' : ''}`}
            >
              {label}
            </button>
          ))}
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
              <li key={movie.id} className="group flex items-center gap-4 py-3">
                <Link to={`/movie/${movie.id}`} className="w-14 shrink-0">
                  <Poster path={movie.poster_path} alt={movie.title} maxWidth={185} sizes="56px" />
                </Link>

                <div className="min-w-0 flex-1">
                  <Link
                    to={`/movie/${movie.id}`}
                    className="block truncate font-display text-sm uppercase tracking-slate text-print-100 hover:text-tungsten-400"
                  >
                    {movie.title}
                  </Link>
                  <p className="mt-1 truncate font-mono text-2xs tabular-nums text-print-500">
                    {movie.year && <span className="tabular-nums">{movie.year}</span>}
                    {movie.genres?.length > 0 && ` · ${movie.genres.slice(0, 2).join(', ')}`}
                    {ratedAt && ` · rated ${new Date(ratedAt).toLocaleDateString()}`}
                  </p>
                </div>

                <RatingStars
                  value={rating}
                  size={17}
                  onChange={(next) =>
                    next
                      ? rate.mutate({ movieId: movie.id, rating: next })
                      : removeRating.mutate(movie.id)
                  }
                />

                <button
                  type="button"
                  onClick={() => removeRating.mutate(movie.id)}
                  aria-label={`Remove your rating of ${movie.title}`}
                  className="btn-ghost h-8 w-8 p-0 opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
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
