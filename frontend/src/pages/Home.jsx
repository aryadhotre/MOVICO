import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Bookmark, BookmarkCheck, Play, Star } from 'lucide-react';
import MovieRow from '../components/MovieRow';
import CueMark from '../components/film/CueMark';
import { backdropSrcSet, backdropUrl } from '../lib/images';
import { timecode } from '../lib/format';
import {
  useHomeFeed,
  useMyRatings,
  useRecommendations,
  useToggleWatchlist,
  useWatchlistIds,
} from '../lib/queries';
import { useAuth } from '../lib/auth';

/** Ratings needed before the fold-in has enough signal to personalise well. */
const RATINGS_TARGET = 10;

/** The opening frame: one film, presented like a title card. */
function Feature({ movie }) {
  const { data: savedIds } = useWatchlistIds();
  const toggleWatchlist = useToggleWatchlist();
  const saved = savedIds?.has(Number(movie.id)) ?? false;

  return (
    <section className="relative overflow-hidden">
      <div className="relative h-[66svh] min-h-[440px] w-full">
        {movie.backdrop_path ? (
          <img
            src={backdropUrl(movie.backdrop_path, 1280)}
            srcSet={backdropSrcSet(movie.backdrop_path)}
            sizes="100vw"
            alt=""
            loading="eager"
            fetchpriority="high"
            decoding="async"
            className="absolute inset-0 h-full w-full animate-slow-zoom object-cover object-top"
          />
        ) : (
          <div className="absolute inset-0 bg-film-850" />
        )}

        <div className="absolute inset-0 bg-gradient-to-t from-film-950 via-film-950/60 to-film-950/25" />
        <div className="absolute inset-0 bg-gradient-to-r from-film-950 via-film-950/45 to-transparent" />
        <div className="absolute inset-0 vignette" />
        <div className="grain absolute inset-0" />
        <CueMark />

        <div className="absolute inset-x-0 bottom-0 p-6 sm:p-10 lg:p-14">
          <div className="max-w-2xl">
            <p className="slate-label mb-4">
              {movie.explanation?.kind === 'cold_start'
                ? 'Now showing'
                : 'Selected for you'}
            </p>

            <h1 className="title-card text-[clamp(1.9rem,5vw,3.75rem)] text-print-50">
              {movie.title}
            </h1>

            <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-2xs tabular-nums text-print-400">
              {movie.year && <span>{movie.year}</span>}
              {movie.runtime > 0 && (
                <>
                  <span className="text-print-100/15">·</span>
                  <span>{timecode(movie.runtime)}</span>
                </>
              )}
              {movie.vote_average > 0 && (
                <>
                  <span className="text-print-100/15">·</span>
                  <span className="flex items-center gap-1 text-tungsten-500">
                    <Star className="h-3 w-3" style={{ fill: 'currentColor' }} />
                    {movie.vote_average.toFixed(1)}
                  </span>
                </>
              )}
              {movie.genres?.length > 0 && (
                <>
                  <span className="text-print-100/15">·</span>
                  <span>{movie.genres.slice(0, 3).join(' / ')}</span>
                </>
              )}
            </div>

            {movie.explanation?.headline && (
              <p className="mt-5 inline-flex max-w-full items-center gap-2 border-l-2 border-tungsten-500 py-1 pl-3 font-mono text-2xs text-print-300">
                <span className="truncate">{movie.explanation.headline}</span>
              </p>
            )}

            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link to={`/movie/${movie.id}`} className="btn-primary">
                <Play className="h-4 w-4" style={{ fill: 'currentColor' }} />
                View film
              </Link>
              <button
                type="button"
                onClick={() => toggleWatchlist.mutate({ movieId: movie.id, saved })}
                className="btn-secondary"
              >
                {saved ? <BookmarkCheck className="h-4 w-4 text-tungsten-500" /> : <Bookmark className="h-4 w-4" />}
                {saved ? 'On your list' : 'Watchlist'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

/** Progress toward a usable taste profile, framed as reel footage. */
function Calibration({ count }) {
  const remaining = Math.max(0, RATINGS_TARGET - count);
  const progress = Math.min(100, (count / RATINGS_TARGET) * 100);

  return (
    <div className="panel flex flex-col gap-6 p-6 sm:flex-row sm:items-center">
      <div className="flex-1">
        <p className="slate-label mb-2">Calibrating</p>
        <h2 className="font-display text-lg font-medium uppercase tracking-slate text-print-50">
          {count === 0
            ? 'Rate a few films to begin'
            : `${remaining} more rating${remaining === 1 ? '' : 's'}`}
        </h2>
        <p className="mt-2 max-w-md text-sm leading-relaxed text-print-400">
          The model needs around {RATINGS_TARGET} ratings to place you. Until then you
          are seeing what is broadly well regarded.
        </p>

        <div className="mt-5 flex items-center gap-3">
          <div className="h-[3px] w-full max-w-sm bg-print-100/10">
            <div
              className="h-full bg-tungsten-500 transition-[width] duration-700 ease-reel"
              style={{ width: `${progress}%` }}
            />
          </div>
          <span className="font-mono text-2xs tabular-nums text-print-500">
            {String(count).padStart(2, '0')}/{RATINGS_TARGET}
          </span>
        </div>
      </div>

      <Link to="/onboarding" className="btn-primary shrink-0">
        Rate films
        <ArrowRight className="h-4 w-4" />
      </Link>
    </div>
  );
}

export default function Home() {
  const { user } = useAuth();
  const { data: feed, isLoading: feedLoading } = useHomeFeed();
  const { data: myRatings } = useMyRatings();
  const { data: recs, isLoading: recsLoading, error: recsError } = useRecommendations({ limit: 20 });

  const ratingCount = Object.keys(myRatings ?? {}).length;
  const isColdStart = ratingCount < RATINGS_TARGET;

  const feature = useMemo(() => {
    const personalised = (recs?.movies ?? []).find((movie) => movie.backdrop_path);
    if (personalised && !isColdStart) return personalised;
    return feed?.hero?.find((movie) => movie.backdrop_path) ?? null;
  }, [recs, feed, isColdStart]);

  const personalRow = useMemo(
    () => (recs?.movies ?? []).filter((movie) => movie.id !== feature?.id),
    [recs, feature],
  );

  return (
    <div>
      {feature ? (
        <Feature movie={feature} />
      ) : (
        feedLoading && <div className="skeleton h-[40svh] w-full" />
      )}

      <div className="mx-auto max-w-[1500px] space-y-14 px-5 py-12 sm:px-8">
        <header className="flex flex-wrap items-end justify-between gap-4 border-b border-print-100/10 pb-6">
          <div>
            <p className="slate-label mb-2">Reel 01</p>
            <h2 className="font-display text-2xl font-medium uppercase tracking-slate text-print-50">
              {user?.username ? `Welcome back, ${user.username}` : 'Welcome back'}
            </h2>
            <p className="tech mt-2 normal-case">
              {ratingCount > 0
                ? `${ratingCount} film${ratingCount === 1 ? '' : 's'} rated`
                : 'No ratings yet'}
            </p>
          </div>
          <Link to="/app/recommendations" className="btn-secondary px-5 py-2.5 text-2xs">
            All selections
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </header>

        {isColdStart && <Calibration count={ratingCount} />}

        {!recsError && (personalRow.length > 0 || recsLoading) && (
          <MovieRow
            title={isColdStart ? 'To get you started' : 'Selected for you'}
            subtitle={
              isColdStart
                ? 'Rate a few of these and the list changes'
                : 'Blended from collaborative and content signal'
            }
            items={personalRow}
            loading={recsLoading}
            priorityCount={4}
          />
        )}

        {feed?.rows?.map((row) => (
          <MovieRow
            key={row.key}
            title={row.title}
            subtitle={row.subtitle}
            items={row.items}
            numbered={row.key === 'trending'}
            spined={row.key === 'acclaimed'}
          />
        ))}

        {feedLoading && <MovieRow title="Trending this week" items={[]} loading />}
      </div>
    </div>
  );
}
