import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Play, Plus, Sparkles, Star } from 'lucide-react';
import MovieRow from '../components/MovieRow';
import { backdropSrcSet, backdropUrl } from '../lib/images';
import {
  useHomeFeed,
  useMyRatings,
  useRecommendations,
  useToggleWatchlist,
  useWatchlistIds,
} from '../lib/queries';
import { useAuth } from '../lib/auth';

/** How many ratings before the model has enough signal to personalise well. */
const RATINGS_TARGET = 10;

function HeroSpotlight({ movie }) {
  const { data: savedIds } = useWatchlistIds();
  const toggleWatchlist = useToggleWatchlist();
  const saved = savedIds?.has(Number(movie.id)) ?? false;

  return (
    <section className="relative -mt-px overflow-hidden">
      <div className="relative h-[62svh] min-h-[420px] w-full">
        {movie.backdrop_path ? (
          <img
            src={backdropUrl(movie.backdrop_path, 1280)}
            srcSet={backdropSrcSet(movie.backdrop_path)}
            sizes="100vw"
            alt=""
            /* Above the fold, so it must not be lazy or low priority. */
            loading="eager"
            fetchpriority="high"
            decoding="async"
            className="absolute inset-0 h-full w-full object-cover object-top"
          />
        ) : (
          <div className="absolute inset-0 bg-ink-850" />
        )}

        {/* Two-axis scrim so the copy is readable over any artwork. */}
        <div className="absolute inset-0 bg-gradient-to-t from-ink-950 via-ink-950/55 to-ink-950/15" />
        <div className="absolute inset-0 bg-gradient-to-r from-ink-950 via-ink-950/40 to-transparent" />

        <div className="absolute inset-x-0 bottom-0 p-6 sm:p-10 lg:p-14">
          <div className="max-w-xl">
            <p className="eyebrow mb-3 flex items-center gap-1.5 text-violet-400">
              <Sparkles className="h-3 w-3" />
              Tonight&apos;s pick for you
            </p>
            <h1 className="text-balance text-3xl font-semibold leading-tight tracking-tightest text-white sm:text-4xl lg:text-5xl">
              {movie.title}
            </h1>

            <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-white/55">
              {movie.year && <span className="tabular-nums">{movie.year}</span>}
              {movie.vote_average > 0 && (
                <span className="flex items-center gap-1 text-amber-500">
                  <Star className="h-3.5 w-3.5" style={{ fill: 'currentColor' }} />
                  <span className="tabular-nums font-semibold">
                    {movie.vote_average.toFixed(1)}
                  </span>
                </span>
              )}
              {movie.genres?.length > 0 && <span>{movie.genres.slice(0, 3).join(' · ')}</span>}
            </div>

            {movie.explanation?.headline && (
              <p className="mt-4 inline-flex max-w-full items-center gap-2 rounded-full border border-violet-600/30 bg-violet-600/10 px-3.5 py-1.5 text-2xs font-medium text-violet-300">
                <Sparkles className="h-3 w-3 shrink-0" />
                <span className="truncate">{movie.explanation.headline}</span>
              </p>
            )}

            <div className="mt-7 flex flex-wrap items-center gap-3">
              <Link to={`/movie/${movie.id}`} className="btn-primary px-6 py-2.5">
                <Play className="h-4 w-4" style={{ fill: 'currentColor' }} />
                View details
              </Link>
              <button
                type="button"
                onClick={() => toggleWatchlist.mutate({ movieId: movie.id, saved })}
                className="btn-secondary px-5 py-2.5"
              >
                <Plus className={`h-4 w-4 transition-transform ${saved ? 'rotate-45' : ''}`} />
                {saved ? 'In watchlist' : 'Watchlist'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function OnboardingNudge({ count }) {
  const remaining = Math.max(0, RATINGS_TARGET - count);
  const progress = Math.min(100, (count / RATINGS_TARGET) * 100);

  return (
    <div className="card-hairline ring-gradient flex flex-col gap-5 p-6 sm:flex-row sm:items-center">
      <div className="flex-1">
        <h2 className="text-lg font-semibold text-white">
          {count === 0
            ? 'Rate a few films to unlock recommendations'
            : `${remaining} more rating${remaining === 1 ? '' : 's'} to go`}
        </h2>
        <p className="mt-1.5 text-sm leading-relaxed text-white/50">
          The model needs around {RATINGS_TARGET} ratings to place you in the taste space.
          Until then you&apos;re seeing what&apos;s broadly popular.
        </p>

        <div className="mt-4 h-1.5 w-full max-w-sm overflow-hidden rounded-full bg-white/[0.07]">
          <div
            className="h-full rounded-full bg-brand-gradient transition-[width] duration-500 ease-smooth"
            style={{ width: `${progress}%` }}
          />
        </div>
        <p className="mt-2 text-2xs tabular-nums text-white/35">
          {count} of {RATINGS_TARGET}
        </p>
      </div>

      <Link to="/onboarding" className="btn-primary shrink-0 px-5 py-2.5">
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
  const { data: recs, isLoading: recsLoading, error: recsError } = useRecommendations({
    limit: 20,
  });

  const ratingCount = Object.keys(myRatings ?? {}).length;
  const isColdStart = ratingCount < RATINGS_TARGET;

  // The spotlight prefers a personalised pick with artwork; it falls back to the
  // catalogue hero when the engine has nothing yet.
  const spotlight = useMemo(() => {
    const personalised = (recs?.movies ?? []).find((movie) => movie.backdrop_path);
    if (personalised && !isColdStart) return personalised;
    return feed?.hero?.find((movie) => movie.backdrop_path) ?? null;
  }, [recs, feed, isColdStart]);

  const personalRow = useMemo(() => {
    const items = recs?.movies ?? [];
    if (items.length === 0) return [];
    // Skip whatever is already occupying the spotlight.
    return items.filter((movie) => movie.id !== spotlight?.id);
  }, [recs, spotlight]);

  const greeting = user?.username ? `Welcome back, ${user.username}` : 'Welcome back';

  return (
    <div>
      {spotlight ? (
        <HeroSpotlight movie={spotlight} />
      ) : (
        <div className="h-[30svh] min-h-[200px]">
          {feedLoading && <div className="skeleton h-full w-full rounded-none" />}
        </div>
      )}

      <div className="mx-auto max-w-[1500px] space-y-12 px-5 py-10 sm:px-6">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="text-2xl font-semibold tracking-tightest text-white">{greeting}</h2>
            <p className="mt-1 text-sm text-white/45">
              {ratingCount > 0
                ? `${ratingCount} film${ratingCount === 1 ? '' : 's'} rated so far`
                : 'Let’s find out what you like'}
            </p>
          </div>
          <Link to="/app/recommendations" className="btn-secondary px-4 py-2 text-sm">
            All recommendations
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </header>

        {isColdStart && <OnboardingNudge count={ratingCount} />}

        {!recsError && (personalRow.length > 0 || recsLoading) && (
          <MovieRow
            title={isColdStart ? 'Popular to get you started' : 'Picked for you'}
            subtitle={
              isColdStart
                ? 'Rate a few of these and the list will change'
                : recs?.strategy === 'hybrid'
                  ? 'Blended from collaborative and content signal'
                  : undefined
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
          />
        ))}

        {feedLoading && <MovieRow title="Trending this week" items={[]} loading />}
      </div>
    </div>
  );
}
