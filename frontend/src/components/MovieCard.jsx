import { memo } from 'react';
import { Link } from 'react-router-dom';
import { Bookmark, BookmarkCheck, Star } from 'lucide-react';
import Poster from './Poster';
import RatingStars from './RatingStars';
import { runtime as formatRuntime } from '../lib/format';
import { useMyRatings, useRateMovie, useToggleWatchlist, useWatchlistIds } from '../lib/queries';
import { useAuth } from '../lib/auth';

/**
 * A catalogue tile.
 *
 * Poster-forward, with the chrome kept off the artwork until it is wanted —
 * the approach Letterboxd and MUBI both take, and the reason their grids read as
 * a wall of film rather than a wall of cards. Metadata sits *below* the poster in
 * monospace instead of being overlaid on it, so nothing obscures the art and every
 * tile aligns on a common baseline.
 *
 * `spine` renders a Criterion-style spine number for curated rows.
 *
 * Memoised because a row renders 20+ of these and an unrelated parent re-render
 * should not re-render every tile.
 */
const MovieCard = memo(function MovieCard({
  movie,
  rank = null,
  spine = null,
  priority = false,
  showRating = true,
  matchScore = null,
  className = '',
}) {
  const { isAuthenticated } = useAuth();
  const { data: myRatings } = useMyRatings();
  const { data: savedIds } = useWatchlistIds();
  const rate = useRateMovie();
  const toggleWatchlist = useToggleWatchlist();

  const myRating = myRatings?.[String(movie.id)] ?? 0;
  const saved = savedIds?.has(Number(movie.id)) ?? false;
  const length = formatRuntime(movie.runtime);

  return (
    <article className={`group relative ${className}`}>
      <Link
        to={`/movie/${movie.id}`}
        className="block outline-none"
        aria-label={`${movie.title}${movie.year ? ` (${movie.year})` : ''}`}
      >
        <div className="relative">
          {/* The frame line: a hairline that warms to tungsten on hover, like a
              light table coming up under the print. */}
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

            {/* Tungsten wash on hover. */}
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

            {/* Spine number, running down the inside edge like a Criterion
                slipcase. It sits inside the frame deliberately: positioned
                outside, the carousel's overflow clips the first card's number
                and every other one lands over the neighbouring poster. */}
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

            {isAuthenticated && (
              <button
                type="button"
                onClick={(event) => {
                  event.preventDefault();
                  toggleWatchlist.mutate({ movieId: movie.id, saved });
                }}
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
          <RatingStars
            value={myRating}
            size={14}
            onChange={(next) => rate.mutate({ movieId: movie.id, rating: next || 0.5 })}
          />
        </div>
      )}
    </article>
  );
});

export default MovieCard;
