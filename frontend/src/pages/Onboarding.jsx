import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { ArrowRight, Check, EyeOff, Loader2, Undo2 } from 'lucide-react';
import Poster from '../components/Poster';
import RatingStars from '../components/RatingStars';
import Logo from '../components/Logo';
import { useToast } from '../components/Toast';
import { useBrowse, useMyRatings, useRateBatch } from '../lib/queries';

/** Enough ratings for the fold-in to place a user meaningfully. */
const TARGET = 10;
const MINIMUM = 5;

export default function Onboarding() {
  const navigate = useNavigate();
  const { data: existing } = useMyRatings();
  const rateBatch = useRateBatch();
  const toast = useToast();

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
        toast.push({ message: `${items.length} ratings saved`, detail: 'Building your profile' });
      } catch {
        // A failed batch must not trap the user here; the ratings they set are
        // recoverable by rating again from any page.
        toast.push({
          kind: 'error',
          message: 'Some ratings did not save',
          detail: 'You can rate again anywhere',
        });
      }
    }
    navigate('/app/recommendations', { replace: true });
  };

  const undoSkip = () => {
    setSkipped((current) => {
      const next = [...current];
      next.pop();
      return new Set(next);
    });
  };

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 border-b border-print-100/[0.08] bg-film-950/90 backdrop-blur-xl">
        <div className="mx-auto max-w-6xl px-5 py-4 sm:px-6">
          <div className="flex items-center justify-between gap-4">
            <Logo size={26} />

            <div className="flex items-center gap-4">
              {/* Ten slots filling as the profile takes shape — a clearer read of
                  "how many more" than a percentage bar on its own. */}
              <div className="hidden items-center gap-1 sm:flex" aria-hidden="true">
                {Array.from({ length: TARGET }, (_, index) => (
                  <motion.span
                    key={index}
                    className={`h-1.5 w-4 ${index < count ? 'bg-tungsten-500' : 'bg-print-100/12'}`}
                    animate={index < count ? { scaleY: [1, 1.8, 1] } : {}}
                    transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
                  />
                ))}
              </div>

              <span className="font-mono text-2xs tabular-nums text-print-400">
                {String(Math.min(count, TARGET)).padStart(2, '0')} / {TARGET}
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

          <div className="mt-4 h-[3px] w-full overflow-hidden bg-print-100/10 sm:hidden">
            <div
              className="h-full bg-tungsten-500 transition-[width] duration-500 ease-reel"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-5 py-10 sm:px-6">
        <div className="mb-10 flex flex-wrap items-end justify-between gap-4">
          <div className="max-w-2xl">
            <p className="slate-label mb-4">Calibration reel</p>
            <h1 className="title-card text-[clamp(1.9rem,5vw,3rem)] text-print-50">
              Rate the ones you&apos;ve seen
            </h1>
            <p className="mt-5 max-w-lg text-pretty text-[15px] leading-relaxed text-print-300">
              Be honest — a film you disliked is as informative as one you loved. Hide
              anything you haven&apos;t watched and it will be replaced.
            </p>
          </div>

          {skipped.size > 0 && (
            <button type="button" onClick={undoSkip} className="btn-secondary px-4 py-2 text-2xs">
              <Undo2 className="h-3.5 w-3.5" />
              Undo hide ({skipped.size})
            </button>
          )}
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
            <AnimatePresence mode="popLayout">
              {candidates.slice(0, 48).map((movie, index) => {
                const rating = picks[movie.id] ?? 0;
                return (
                  <motion.div
                    key={movie.id}
                    layout
                    // Hidden titles collapse out and the grid closes the gap, so the
                    // sheet stays dense instead of developing holes.
                    exit={{ opacity: 0, scale: 0.92 }}
                    transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
                    className="group relative"
                  >
                    <div
                      className={`relative overflow-hidden border transition-all duration-300 ease-reel ${
                        rating
                          ? 'border-tungsten-500 shadow-halate'
                          : 'border-print-100/10 hover:border-print-100/30'
                      }`}
                    >
                      <Poster
                        path={movie.poster_path}
                        alt={movie.title}
                        priority={index < 8}
                        maxWidth={342}
                        rounded="rounded-none"
                      />

                      {rating > 0 && (
                        <motion.span
                          initial={{ scale: 0 }}
                          animate={{ scale: 1 }}
                          className="absolute right-0 top-0 flex h-6 w-6 items-center justify-center bg-tungsten-500 text-film-950"
                        >
                          <Check className="h-3.5 w-3.5" strokeWidth={3} />
                        </motion.span>
                      )}

                      <button
                        type="button"
                        onClick={() => setSkipped((current) => new Set(current).add(movie.id))}
                        aria-label={`I haven't seen ${movie.title}`}
                        className="absolute left-0 top-0 flex h-6 w-6 items-center justify-center bg-film-950/85 text-print-300 opacity-0 backdrop-blur transition-opacity hover:text-tungsten-400 focus-visible:opacity-100 group-hover:opacity-100"
                      >
                        <EyeOff className="h-3 w-3" />
                      </button>
                    </div>

                    <p className="clamp-2 mt-2.5 font-display text-2xs uppercase leading-snug tracking-slate text-print-200">
                      {movie.title}
                    </p>
                    {movie.year && (
                      <p className="mt-1 font-mono text-[10px] tabular-nums text-print-500">
                        {movie.year}
                      </p>
                    )}

                    <div className="mt-2 flex justify-center">
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
                  </motion.div>
                );
              })}
            </AnimatePresence>
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
