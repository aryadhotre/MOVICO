import { memo, useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { Bookmark, BookmarkCheck, Info, Star } from 'lucide-react';
import Poster from './Poster';
import RatingStars from './RatingStars';
import { useToast } from './Toast';
import { backdropUrl } from '../lib/images';
import { runtime as formatRuntime } from '../lib/format';
import { useMyRatings, useRateMovie, useToggleWatchlist, useWatchlistIds } from '../lib/queries';
import { useAuth } from '../lib/auth';

/** Delay before a hover counts as intent, so sweeping across a row stays quiet. */
const HOVER_INTENT_MS = 420;

/**
 * The expanded panel a card raises on sustained hover.
 *
 * Netflix's pattern — enough metadata to decide without leaving the row — with
 * Apple TV+'s restraint: no autoplaying video, nothing that moves on its own, and
 * it only appears on a deliberate hover. Pointer-only by design; touch devices get
 * the detail page, which is the better target anyway.
 */
function HoverPanel({ movie, saved, myRating, onRate, onToggleSave, align }) {
  const length = formatRuntime(movie.runtime);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 4, scale: 0.98 }}
      transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
      className={`absolute bottom-full z-30 mb-2 hidden w-[19rem] border border-tungsten-500/35
                  bg-film-850/97 shadow-lift backdrop-blur-xl lg:block
                  ${align === 'right' ? 'right-0' : 'left-0'}`}
      // The panel belongs to the card's hover region; the card handles enter/leave.
      onClick={(event) => event.stopPropagation()}
    >
      {movie.backdrop_path && (
        <div className="relative h-28 overflow-hidden">
          <img
            src={backdropUrl(movie.backdrop_path, 300)}
            alt=""
            loading="lazy"
            decoding="async"
            className="h-full w-full object-cover"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-film-850 via-film-850/40 to-transparent" />
        </div>
      )}

      <div className="p-4">
        <h4 className="font-display text-sm uppercase tracking-slate text-print-50">
          {movie.title}
        </h4>

        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[10px] tabular-nums text-print-400">
          {movie.year && <span>{movie.year}</span>}
          {length && <span>{length}</span>}
          {movie.vote_average > 0 && (
            <span className="flex items-center gap-1 text-tungsten-500">
              <Star className="h-2.5 w-2.5" style={{ fill: 'currentColor' }} />
              {movie.vote_average.toFixed(1)}
            </span>
          )}
          {movie.rating_count > 0 && <span>{movie.rating_count.toLocaleString()} ratings</span>}
        </div>

        {movie.genres?.length > 0 && (
          <p className="mt-2.5 font-mono text-[10px] uppercase tracking-wider text-print-500">
            {movie.genres.slice(0, 3).join(' · ')}
          </p>
        )}

        <div className="mt-4 flex items-center justify-between gap-3 border-t border-print-100/10 pt-3">
          <RatingStars value={myRating} size={15} onChange={onRate} />
          <button
            type="button"
            onClick={onToggleSave}
            aria-label={saved ? 'Remove from watchlist' : 'Save to watchlist'}
            className={`transition-colors ${
              saved ? 'text-tungsten-500' : 'text-print-400 hover:text-tungsten-400'
            }`}
          >
            {saved ? <BookmarkCheck className="h-4 w-4" /> : <Bookmark className="h-4 w-4" />}
          </button>
        </div>
      </div>
    </motion.div>
  );
}

/**
 * A catalogue tile.
 *
 * Poster-forward with the metadata set below the artwork rather than over it —
 * the approach Letterboxd and MUBI share, and the reason their grids read as a
 * wall of film rather than a wall of cards.
 *
 * Memoised: a row renders 20+ of these and an unrelated parent re-render should
 * not re-render every tile.
 */
const MovieCard = memo(function MovieCard({
  movie,
  rank = null,
  spine = null,
  priority = false,
  showRating = true,
  matchScore = null,
  preview = true,
  className = '',
}) {
  const { isAuthenticated } = useAuth();
  const { data: myRatings } = useMyRatings();
  const { data: savedIds } = useWatchlistIds();
  const rate = useRateMovie();
  const toggleWatchlist = useToggleWatchlist();
  const toast = useToast();

  const [hovered, setHovered] = useState(false);
  const [align, setAlign] = useState('left');
  const timer = useRef(null);
  const container = useRef(null);

  const myRating = myRatings?.[String(movie.id)] ?? 0;
  const saved = savedIds?.has(Number(movie.id)) ?? false;
  const length = formatRuntime(movie.runtime);

  useEffect(() => () => clearTimeout(timer.current), []);

  const openPreview = useCallback(() => {
    if (!preview || !isAuthenticated) return;
    clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      // Flip the panel inward when the card sits near the right edge, so it can
      // never open off-screen.
      const box = container.current?.getBoundingClientRect();
      if (box) setAlign(box.left + 320 > window.innerWidth ? 'right' : 'left');
      setHovered(true);
    }, HOVER_INTENT_MS);
  }, [preview, isAuthenticated]);

  const closePreview = useCallback(() => {
    clearTimeout(timer.current);
    setHovered(false);
  }, []);

  const handleRate = useCallback(
    (next) => {
      const value = next || 0.5;
      rate.mutate(
        { movieId: movie.id, rating: value },
        {
          onError: () =>
            toast.push({ kind: 'error', message: 'Could not save rating', detail: movie.title }),
        },
      );
      toast.push({ kind: 'rating', message: `Rated ${value.toFixed(1)}`, detail: movie.title });
    },
    [rate, movie.id, movie.title, toast],
  );

  const handleToggleSave = useCallback(
    (event) => {
      event?.preventDefault?.();
      toggleWatchlist.mutate(
        { movieId: movie.id, saved },
        {
          onError: () =>
            toast.push({ kind: 'error', message: 'Could not update watchlist', detail: movie.title }),
        },
      );
      toast.push({
        kind: 'watchlist',
        message: saved ? 'Removed from watchlist' : 'Saved to watchlist',
        detail: movie.title,
      });
    },
    [toggleWatchlist, movie.id, movie.title, saved, toast],
  );

  return (
    <article
      ref={container}
      className={`group relative ${className}`}
      onMouseEnter={openPreview}
      onMouseLeave={closePreview}
    >
      <AnimatePresence>
        {hovered && (
          <HoverPanel
            movie={movie}
            saved={saved}
            myRating={myRating}
            align={align}
            onRate={handleRate}
            onToggleSave={handleToggleSave}
          />
        )}
      </AnimatePresence>

      <Link
        to={`/movie/${movie.id}`}
        className="block outline-none"
        aria-label={`${movie.title}${movie.year ? ` (${movie.year})` : ''}`}
      >
        <div className="relative">
          {/* The frame line warms to tungsten on hover, like a light table coming
              up under the print. */}
          <div
            className="relative overflow-hidden border border-print-100/10 shadow-print
                       transition-all duration-300 ease-reel
                       group-hover:-translate-y-1 group-hover:border-tungsten-500/70 group-hover:shadow-lift"
          >
            <Poster
              path={movie.poster_path}
              alt={movie.title}
              priority={priority}
              maxWidth={342}
              rounded="rounded-none"
            />

            <div className="pointer-events-none absolute inset-0 bg-tungsten-500/0 transition-colors duration-300 group-hover:bg-tungsten-500/[0.07]" />

            {rank !== null && (
              <span className="absolute left-0 top-0 flex h-7 min-w-7 items-center justify-center bg-film-950/90 px-1.5 font-mono text-2xs font-bold tabular-nums text-tungsten-400 backdrop-blur">
                {String(rank).padStart(2, '0')}
              </span>
            )}

            {matchScore !== null && (
              <span className="absolute right-0 top-0 bg-tungsten-500 px-2 py-1 font-mono text-2xs font-bold tabular-nums text-film-950">
                {matchScore}%
              </span>
            )}

            {/* Spine number, inside the frame: positioned outside, the carousel's
                overflow clips the first card's number and every other one lands
                over the neighbouring poster. */}
            {spine !== null && (
              <span
                className="absolute bottom-0 left-0 top-0 hidden w-5 items-end justify-center
                           bg-gradient-to-r from-film-950/80 to-transparent pb-3
                           font-mono text-[10px] tabular-nums text-print-300 sm:flex"
                style={{ writingMode: 'vertical-rl', textOrientation: 'mixed' }}
              >
                № {String(spine).padStart(3, '0')}
              </span>
            )}

            {/* A rated film keeps a persistent tungsten rule along its foot. */}
            {myRating > 0 && (
              <span
                className="absolute inset-x-0 bottom-0 h-[3px] bg-tungsten-500"
                style={{ opacity: Math.max(0.35, myRating / 5) }}
                aria-hidden="true"
              />
            )}

            {isAuthenticated && (
              <button
                type="button"
                onClick={handleToggleSave}
                aria-label={saved ? `Remove ${movie.title} from watchlist` : `Save ${movie.title}`}
                aria-pressed={saved}
                className={`absolute bottom-0 right-0 flex h-9 w-9 items-center justify-center
                            bg-film-950/85 backdrop-blur transition-all duration-200
                            hover:text-tungsten-400 focus-visible:opacity-100
                            ${saved ? 'text-tungsten-500 opacity-100' : 'text-print-200 opacity-0 group-hover:opacity-100'}`}
              >
                {saved ? <BookmarkCheck className="h-4 w-4" /> : <Bookmark className="h-4 w-4" />}
              </button>
            )}
          </div>
        </div>

        <div className="mt-2.5">
          <h3 className="clamp-2 font-display text-sm font-medium leading-tight text-print-100 transition-colors group-hover:text-tungsten-400">
            {movie.title}
          </h3>

          <div className="mt-1 flex items-center gap-2 font-mono text-2xs tabular-nums text-print-500">
            {movie.year && <span>{movie.year}</span>}
            {length && (
              <>
                <span className="text-print-100/15">·</span>
                <span>{length}</span>
              </>
            )}
            {movie.vote_average > 0 && (
              <>
                <span className="text-print-100/15">·</span>
                <span className="flex items-center gap-0.5 text-tungsten-500">
                  <Star className="h-2.5 w-2.5" style={{ fill: 'currentColor' }} />
                  {movie.vote_average.toFixed(1)}
                </span>
              </>
            )}
          </div>
        </div>
      </Link>

      {isAuthenticated && showRating && (
        <div
          className={`mt-1.5 transition-opacity duration-200 ${
            myRating ? 'opacity-100' : 'opacity-0 focus-within:opacity-100 group-hover:opacity-100'
          }`}
        >
          <RatingStars value={myRating} size={14} onChange={handleRate} />
        </div>
      )}
    </article>
  );
});

export default MovieCard;
