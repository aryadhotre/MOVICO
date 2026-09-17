import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, Check, EyeOff, Loader2 } from 'lucide-react';
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
      <header className="sticky top-0 z-40 border-b border-print-100/[0.08] bg-film-950/90 backdrop-blur-xl">
        <div className="mx-auto max-w-6xl px-5 py-4 sm:px-6">
          <div className="flex items-center justify-between gap-4">
            <Logo size={26} />
            <div className="flex items-center gap-4">
              <span className="hidden font-mono text-2xs tabular-nums text-print-400 sm:inline">
                {String(count).padStart(2, '0')} / {TARGET}
              </span>
              <button
                type="button"
                onClick={finish}
                disabled={!canContinue || rateBatch.isPending}
                className="btn-primary px-5 py-2.5 text-2xs"
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

          <div className="mt-4 h-[3px] w-full overflow-hidden bg-print-100/10">
            <div
              className="h-full bg-tungsten-500 transition-[width] duration-500 ease-reel"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-5 py-10 sm:px-6">
        <div className="mb-10 max-w-2xl">
          <p className="slate-label mb-4">Calibration reel</p>
          <h1 className="title-card text-[clamp(1.9rem,5vw,3rem)] text-print-50">
            Rate the ones you&apos;ve seen
          </h1>
          <p className="mt-5 max-w-lg text-pretty text-[15px] leading-relaxed text-print-300">
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
                    className={`relative overflow-hidden border transition-all duration-300 ease-reel ${
                      rating ? 'border-tungsten-500' : 'border-print-100/10'
                    }`}
                  >
                    <Poster
                      path={movie.poster_path}
                      alt={movie.title}
                      priority={index < 8}
                      maxWidth={342}
                    />

                    {rating > 0 && (
                      <span className="absolute right-0 top-0 flex h-6 w-6 items-center justify-center bg-tungsten-500 text-film-950">
                        <Check className="h-3.5 w-3.5" strokeWidth={3} />
                      </span>
                    )}

                    <button
                      type="button"
                      onClick={() =>
                        setSkipped((current) => new Set(current).add(movie.id))
                      }
                      aria-label={`I haven't seen ${movie.title}`}
                      className="absolute left-0 top-0 flex h-6 w-6 items-center justify-center bg-film-950/85 text-print-300 opacity-0 backdrop-blur transition-opacity hover:text-tungsten-400 group-hover:opacity-100 focus-visible:opacity-100"
                    >
                      <EyeOff className="h-3 w-3" />
                    </button>
                  </div>

                  <p className="clamp-2 mt-2.5 font-display text-2xs uppercase leading-snug tracking-slate text-print-200">
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
              className="btn-secondary"
            >
              {isFetchingNextPage && <Loader2 className="h-4 w-4 animate-spin" />}
              Show more films
            </button>
          </div>
        )}

        <p className="tech mt-14 text-center normal-case">
          You can always{' '}
          <Link to="/app" className="text-print-200 underline underline-offset-4 hover:text-tungsten-400">
            skip for now
          </Link>{' '}
          and rate films as you browse.
        </p>
      </div>
    </div>
  );
}
