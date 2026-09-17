import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, Check, EyeOff, Loader2, Sparkles } from 'lucide-react';
import Poster from '../components/Poster';
import RatingStars from '../components/RatingStars';
import Logo from '../components/Logo';
import { useBrowse, useMyRatings, useRateBatch } from '../lib/queries';

/** Enough ratings for the fold-in to place a user meaningfully. */
const TARGET = 10;
const MINIMUM = 5;

export default function Onboarding() {
  const navigate = useNavigate();
  const { data: existing } = useMyRatings();
  const rateBatch = useRateBatch();

  const [picks, setPicks] = useState({});
  const [skipped, setSkipped] = useState(() => new Set());

  // Sorted by how many people have rated them: these are the films someone is
  // most likely to have actually seen, which is what makes the grid answerable.
  const { data, isLoading, hasNextPage, fetchNextPage, isFetchingNextPage } = useBrowse({
    sort_by: 'votes',
    order: 'desc',
    min_rating: 3.4,
    page_size: 36,
  });

  const candidates = useMemo(() => {
    const alreadyRated = new Set(Object.keys(existing ?? {}).map(Number));
    return (data?.pages ?? [])
      .flatMap((page) => page.items ?? [])
      .filter((movie) => !alreadyRated.has(movie.id) && !skipped.has(movie.id));
  }, [data, existing, skipped]);

  const count = Object.keys(picks).length + Object.keys(existing ?? {}).length;
  const progress = Math.min(100, (count / TARGET) * 100);
  const canContinue = count >= MINIMUM;

  const finish = async () => {
    const items = Object.entries(picks).map(([movieId, rating]) => ({
      movie_id: Number(movieId),
      rating,
    }));
    if (items.length > 0) {
      try {
        await rateBatch.mutateAsync(items);
      } catch {
        // A failed batch should not trap the user in onboarding; the ratings they
        // set are recoverable by rating again from any page.
      }
    }
    navigate('/app/recommendations', { replace: true });
  };

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 border-b border-white/[0.06] bg-ink-950/85 backdrop-blur-xl">
        <div className="mx-auto max-w-6xl px-5 py-4 sm:px-6">
          <div className="flex items-center justify-between gap-4">
            <Logo size={26} />
            <div className="flex items-center gap-4">
              <span className="hidden text-2xs tabular-nums text-white/45 sm:inline">
                {count} of {TARGET} rated
              </span>
              <button
                type="button"
                onClick={finish}
                disabled={!canContinue || rateBatch.isPending}
                className="btn-primary px-5 py-2"
              >
                {rateBatch.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <ArrowRight className="h-4 w-4" />
                )}
                {canContinue ? 'See my recommendations' : `Rate ${MINIMUM - count} more`}
              </button>
            </div>
          </div>

          <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-white/[0.07]">
            <div
              className="h-full rounded-full bg-brand-gradient transition-[width] duration-500 ease-smooth"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-5 py-10 sm:px-6">
        <div className="mb-10 max-w-2xl">
          <p className="eyebrow mb-3 flex items-center gap-1.5 text-violet-400">
            <Sparkles className="h-3 w-3" />
            Building your taste profile
          </p>
          <h1 className="text-balance text-3xl font-semibold tracking-tightest text-white sm:text-4xl">
            Rate the ones you&apos;ve seen
          </h1>
          <p className="mt-3 text-pretty text-[15px] leading-relaxed text-white/50">
            Be honest — a film you disliked is as informative as one you loved. Hide anything
            you haven&apos;t watched and it will be replaced.
          </p>
        </div>

        {isLoading ? (
          <div
            className="grid gap-x-4 gap-y-8"
            style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(clamp(130px, 15vw, 170px), 1fr))' }}
          >
            {Array.from({ length: 18 }, (_, index) => (
              <div key={index}>
                <div className="skeleton aspect-[2/3] w-full" />
                <div className="skeleton mt-2 h-3 w-4/5" />
              </div>
            ))}
          </div>
        ) : (
          <div
            className="grid gap-x-4 gap-y-8"
            style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(clamp(130px, 15vw, 170px), 1fr))' }}
          >
            {candidates.slice(0, 48).map((movie, index) => {
              const rating = picks[movie.id] ?? 0;
              return (
                <div key={movie.id} className="group relative">
                  <div
                    className={`relative overflow-hidden rounded-xl transition-all duration-300 ease-smooth ${
                      rating
                        ? 'ring-2 ring-violet-500 ring-offset-2 ring-offset-ink-950'
                        : 'ring-0'
                    }`}
                  >
                    <Poster
                      path={movie.poster_path}
                      alt={movie.title}
                      priority={index < 8}
                      maxWidth={342}
                    />

                    {rating > 0 && (
                      <span className="absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-full bg-violet-600 text-white shadow-glow">
                        <Check className="h-3.5 w-3.5" strokeWidth={3} />
                      </span>
                    )}

                    <button
                      type="button"
                      onClick={() =>
                        setSkipped((current) => new Set(current).add(movie.id))
                      }
                      aria-label={`I haven't seen ${movie.title}`}
                      className="absolute left-2 top-2 flex h-6 w-6 items-center justify-center rounded-full bg-ink-950/75 text-white/65 opacity-0 backdrop-blur ring-1 ring-white/15 transition-opacity hover:text-white group-hover:opacity-100 focus-visible:opacity-100"
                    >
                      <EyeOff className="h-3 w-3" />
                    </button>
                  </div>

                  <p className="clamp-2 mt-2 text-2xs font-medium leading-snug text-white/70">
                    {movie.title}
                  </p>

                  <div className="mt-1.5 flex justify-center">
                    <RatingStars
                      value={rating}
                      size={16}
                      onChange={(next) =>
                        setPicks((current) => {
                          const updated = { ...current };
                          if (!next) delete updated[movie.id];
                          else updated[movie.id] = next;
                          return updated;
                        })
                      }
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {hasNextPage && (
          <div className="mt-12 flex justify-center">
            <button
              type="button"
              onClick={() => fetchNextPage()}
              disabled={isFetchingNextPage}
              className="btn-secondary px-6 py-2.5"
            >
              {isFetchingNextPage && <Loader2 className="h-4 w-4 animate-spin" />}
              Show more films
            </button>
          </div>
        )}

        <p className="mt-12 text-center text-2xs text-white/30">
          You can always{' '}
          <Link to="/app" className="text-white/50 underline underline-offset-2 hover:text-white">
            skip for now
          </Link>{' '}
          and rate films as you browse.
        </p>
      </div>
    </div>
  );
}
