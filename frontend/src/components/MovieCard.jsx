import { memo } from 'react';
import { Link } from 'react-router-dom';
import { Bookmark, BookmarkCheck, Sparkles, Star } from 'lucide-react';
import Poster from './Poster';
import RatingStars from './RatingStars';
import { useMyRatings, useRateMovie, useToggleWatchlist, useWatchlistIds } from '../lib/queries';
import { useAuth } from '../lib/auth';

function formatRuntime(minutes) {
  if (!minutes) return null;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return hours ? `${hours}h ${rest}m` : `${rest}m`;
}

/**
 * A catalogue tile.
 *
 * Rating and watchlist controls live on the card itself so a user can build a
 * taste profile without opening a detail page — that loop is what turns a cold
 * account into useful recommendations. Both are optimistic, so the star fills
 * before the request finishes.
 *
 * Memoised because rows render 20+ of these and a parent re-render (a hover
 * elsewhere, a route transition) should not re-render every tile.
 */
const MovieCard = memo(function MovieCard({
  movie,
  rank = null,
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
  const runtime = formatRuntime(movie.runtime);

  return (
    <div className={`group relative ${className}`}>
      <Link
        to={`/movie/${movie.id}`}
        className="block outline-none"
        aria-label={`${movie.title}${movie.year ? ` (${movie.year})` : ''}`}
      >
        <div className="relative overflow-hidden rounded-xl shadow-card transition-all duration-300 ease-smooth group-hover:-translate-y-1.5 group-hover:shadow-lift">
          <Poster
            path={movie.poster_path}
            alt={movie.title}
            priority={priority}
            maxWidth={342}
          />

          {/* Readability scrim, deepened on hover so the meta row stays legible. */}
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-ink-950 via-ink-950/25 to-transparent opacity-80 transition-opacity duration-300 group-hover:opacity-95" />

          {rank !== null && (
            <div className="absolute left-2 top-2 flex h-7 w-7 items-center justify-center rounded-lg bg-ink-950/75 text-xs font-bold text-white backdrop-blur-md ring-1 ring-white/15">
              {rank}
            </div>
          )}

          {matchScore !== null && (
            <div className="absolute right-2 top-2 flex items-center gap-1 rounded-full bg-violet-600/90 px-2 py-0.5 text-2xs font-bold text-white shadow-glow backdrop-blur-sm">
              <Sparkles className="h-3 w-3" />
              {matchScore}%
            </div>
          )}

          <div className="absolute inset-x-0 bottom-0 p-3">
            <h3 className="clamp-2 text-sm font-semibold leading-snug tracking-snug text-white drop-shadow">
              {movie.title}
            </h3>
            <div className="mt-1 flex items-center gap-2 text-2xs font-medium text-white/60">
              {movie.year && <span className="tabular-nums">{movie.year}</span>}
              {runtime && (
                <>
                  <span aria-hidden="true">·</span>
                  <span>{runtime}</span>
                </>
              )}
              {movie.vote_average > 0 && (
                <>
                  <span aria-hidden="true">·</span>
                  <span className="flex items-center gap-0.5 text-amber-500">
                    <Star className="h-3 w-3" style={{ fill: 'currentColor' }} />
                    <span className="tabular-nums">{movie.vote_average.toFixed(1)}</span>
                  </span>
                </>
              )}
            </div>
          </div>
        </div>
      </Link>

      {isAuthenticated && (
        <>
          <button
            type="button"
            onClick={() => toggleWatchlist.mutate({ movieId: movie.id, saved })}
            aria-label={saved ? `Remove ${movie.title} from watchlist` : `Save ${movie.title} to watchlist`}
            aria-pressed={saved}
            className={`absolute right-2 top-2 flex h-8 w-8 items-center justify-center rounded-full bg-ink-950/70 text-white/80 backdrop-blur-md ring-1 ring-white/15 transition-all duration-200
              hover:scale-110 hover:text-white focus-visible:opacity-100
              ${saved ? 'opacity-100 text-violet-400' : 'opacity-0 group-hover:opacity-100'}
              ${matchScore !== null ? 'top-10' : ''}`}
          >
            {saved ? <BookmarkCheck className="h-4 w-4" /> : <Bookmark className="h-4 w-4" />}
          </button>

          {showRating && (
            <div
              className={`mt-2 flex justify-center transition-opacity duration-200 ${
                myRating ? 'opacity-100' : 'opacity-0 group-hover:opacity-100 focus-within:opacity-100'
              }`}
            >
              <RatingStars
                value={myRating}
                size={15}
                onChange={(next) => rate.mutate({ movieId: movie.id, rating: next || 0.5 })}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
});

export default MovieCard;
