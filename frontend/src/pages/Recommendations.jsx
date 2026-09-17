import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, RefreshCw, Shuffle, Sparkles, SlidersHorizontal, Star } from 'lucide-react';
import MovieCard from '../components/MovieCard';
import ExplanationCard from '../components/ExplanationCard';
import EmptyState from '../components/EmptyState';
import { useGenres, useMyRatings, useRecommendations } from '../lib/queries';

/**
 * Converts the engine's blended score into a "match" percentage.
 *
 * The raw score is a weighted sum of z-scores, so it has no natural ceiling and is
 * meaningless to a user. Ranking the returned set and mapping position onto a band
 * is honest about what it represents — relative order within this list — rather than
 * implying a calibrated probability the model never produced.
 */
function withMatchScores(movies) {
  if (!movies?.length) return [];
  return movies.map((movie, index) => ({
    ...movie,
    matchScore: Math.round(97 - (index / Math.max(movies.length - 1, 1)) * 24),
  }));
}

function Slider({ label, hint, value, onChange, min = 0, max = 1, step = 0.1 }) {
  return (
    <label className="block">
      <span className="flex items-center justify-between text-2xs font-medium text-white/60">
        {label}
        <span className="tabular-nums text-white/35">{Math.round(value * 100)}%</span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="mt-2 h-1.5 w-full cursor-pointer appearance-none rounded-full bg-white/[0.09]
                   [&::-webkit-slider-thumb]:h-3.5 [&::-webkit-slider-thumb]:w-3.5
                   [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full
                   [&::-webkit-slider-thumb]:bg-violet-500 [&::-webkit-slider-thumb]:shadow-glow
                   [&::-moz-range-thumb]:h-3.5 [&::-moz-range-thumb]:w-3.5
                   [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border-0
                   [&::-moz-range-thumb]:bg-violet-500"
      />
      {hint && <span className="mt-1.5 block text-2xs leading-relaxed text-white/30">{hint}</span>}
    </label>
  );
}

export default function Recommendations() {
  const [diversity, setDiversity] = useState(1);
  const [novelty, setNovelty] = useState(0);
  const [genre, setGenre] = useState('');
  const [expanded, setExpanded] = useState(null);
  const [showControls, setShowControls] = useState(false);

  const { data: genreData } = useGenres();
  const { data: myRatings } = useMyRatings();
  const ratingCount = Object.keys(myRatings ?? {}).length;

  const params = useMemo(
    () => ({
      limit: 40,
      diversity,
      novelty,
      ...(genre ? { genres: genre } : {}),
    }),
    [diversity, novelty, genre],
  );

  const { data, isLoading, isFetching, error, refetch } = useRecommendations(params);
  const movies = useMemo(() => withMatchScores(data?.movies), [data]);

  const topGenres = (genreData?.genres ?? []).slice(0, 12);

  if (error) {
    const untrained = error.status === 503;
    return (
      <div className="mx-auto max-w-2xl px-5 py-20">
        <div className="card-hairline p-8 text-center">
          <AlertTriangle className="mx-auto h-8 w-8 text-amber-500" strokeWidth={1.6} />
          <h1 className="mt-4 text-xl font-semibold text-white">
            {untrained ? 'The model is not loaded yet' : 'Could not load recommendations'}
          </h1>
          <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-white/50">
            {untrained
              ? 'The recommendation engine has no trained artifacts on disk. Run the training pipeline, then reload.'
              : error.message}
          </p>
          <button type="button" onClick={() => refetch()} className="btn-secondary mt-6 px-5 py-2.5">
            <RefreshCw className="h-4 w-4" />
            Try again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1500px] px-5 py-8 sm:px-6">
      <header className="mb-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="eyebrow mb-2 flex items-center gap-1.5 text-violet-400">
              <Sparkles className="h-3 w-3" />
              {data?.strategy === 'cold_start' ? 'Warming up' : 'Hybrid engine'}
            </p>
            <h1 className="text-3xl font-semibold tracking-tightest text-white">For you</h1>
            <p className="mt-1.5 text-sm text-white/45">
              {data
                ? `${movies.length} films · computed in ${data.execution_ms.toFixed(0)}ms${
                    data.cached ? ' (cached)' : ''
                  }`
                : 'Ranking the catalogue…'}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowControls((open) => !open)}
              className={`btn-secondary px-4 py-2 text-sm ${showControls ? 'border-white/25' : ''}`}
              aria-expanded={showControls}
            >
              <SlidersHorizontal className="h-4 w-4" />
              Tune
            </button>
            <button
              type="button"
              onClick={() => refetch()}
              disabled={isFetching}
              className="btn-icon"
              aria-label="Refresh recommendations"
            >
              <RefreshCw className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {showControls && (
          <div className="mt-5 grid gap-6 rounded-2xl border border-white/[0.07] bg-ink-900/50 p-5 sm:grid-cols-2">
            <Slider
              label="Diversity"
              hint="Higher spreads picks across genres instead of clustering on one."
              value={diversity}
              onChange={setDiversity}
            />
            <Slider
              label="Novelty"
              hint="Higher pushes toward the long tail and away from well-known titles."
              value={novelty}
              onChange={setNovelty}
            />

            <div className="sm:col-span-2">
              <span className="mb-2 block text-2xs font-medium text-white/60">Restrict to genre</span>
              <div className="flex flex-wrap gap-1.5">
                <button
                  type="button"
                  onClick={() => setGenre('')}
                  className={`chip ${!genre ? 'chip-active' : ''}`}
                >
                  Any
                </button>
                {topGenres.map(({ name }) => (
                  <button
                    key={name}
                    type="button"
                    onClick={() => setGenre(name === genre ? '' : name)}
                    className={`chip ${genre === name ? 'chip-active' : ''}`}
                  >
                    {name}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </header>

      {ratingCount < 5 && !isLoading && (
        <div className="mb-8 flex flex-wrap items-center justify-between gap-4 rounded-xl border border-violet-600/25 bg-violet-600/[0.07] px-5 py-4">
          <p className="text-sm text-white/70">
            <Star className="mr-1.5 inline h-3.5 w-3.5 text-amber-500" />
            With {ratingCount} rating{ratingCount === 1 ? '' : 's'} these are mostly popular picks.
            Rate a few more to personalise them.
          </p>
          <Link to="/onboarding" className="btn-primary px-4 py-2 text-sm">
            Rate films
          </Link>
        </div>
      )}

      {isLoading ? (
        <div
          className="grid gap-x-4 gap-y-6"
          style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(clamp(130px, 15vw, 180px), 1fr))' }}
        >
          {Array.from({ length: 18 }, (_, index) => (
            <div key={index}>
              <div className="skeleton aspect-[2/3] w-full" />
              <div className="skeleton mt-2 h-3 w-4/5" />
            </div>
          ))}
        </div>
      ) : movies.length === 0 ? (
        <EmptyState
          icon={Shuffle}
          title="Nothing matched those filters"
          description="Try widening the genre restriction or lowering novelty."
        />
      ) : (
        <div
          className="grid gap-x-4 gap-y-6"
          style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(clamp(130px, 15vw, 180px), 1fr))' }}
        >
          {movies.map((movie, index) => (
            <div key={movie.id} className="flex flex-col">
              <MovieCard movie={movie} matchScore={movie.matchScore} priority={index < 6} />

              {movie.explanation && (
                <>
                  <button
                    type="button"
                    onClick={() => setExpanded(expanded === movie.id ? null : movie.id)}
                    className="mt-2 text-left"
                    aria-expanded={expanded === movie.id}
                  >
                    <ExplanationCard explanation={movie.explanation} compact />
                  </button>

                  {expanded === movie.id && (
                    <div className="mt-2 animate-fade-up">
                      <ExplanationCard explanation={movie.explanation} />
                    </div>
                  )}
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
