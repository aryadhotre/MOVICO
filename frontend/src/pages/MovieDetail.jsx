import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { ArrowLeft, Bookmark, BookmarkCheck, Film, Play, Star, X } from 'lucide-react';
import MovieRow from '../components/MovieRow';
import CastRail from '../components/CastRail';
import { useToast } from '../components/Toast';
import RatingStars from '../components/RatingStars';
import Poster from '../components/Poster';
import PageSpinner from '../components/PageSpinner';
import CueMark from '../components/film/CueMark';
import SpecSheet from '../components/film/SpecSheet';
import { backdropSrcSet, backdropUrl, youtubeEmbed } from '../lib/images';
import { compact, era, inferAspectRatio, languageName, reelCode, timecode } from '../lib/format';
import {
  useMovie,
  useMyRatings,
  useRateMovie,
  useSimilar,
  useToggleWatchlist,
  useWatchlistIds,
} from '../lib/queries';
import { useAuth } from '../lib/auth';

function TrailerModal({ trailerKey, title, onClose }) {
  return (
    <AnimatePresence>
      {trailerKey && (
        <motion.div
          className="fixed inset-0 z-[80] flex items-center justify-center p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <div className="absolute inset-0 bg-film-950/94 backdrop-blur-sm" onClick={onClose} />
          <motion.div
            className="relative w-full max-w-5xl border border-print-100/15 bg-black shadow-lift"
            initial={{ scale: 0.97, y: 12 }}
            animate={{ scale: 1, y: 0 }}
            exit={{ scale: 0.98, opacity: 0 }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="flex items-center justify-between border-b border-print-100/15 px-4 py-2">
              <span className="tech">Trailer · {title}</span>
              <button type="button" onClick={onClose} aria-label="Close trailer" className="btn-ghost h-7 w-7 p-0">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="aspect-video w-full">
              <iframe
                src={youtubeEmbed(trailerKey)}
                title={`${title} trailer`}
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowFullScreen
                className="h-full w-full"
              />
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export default function MovieDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const [trailerOpen, setTrailerOpen] = useState(false);

  const { data: movie, isLoading, error } = useMovie(id);
  const { data: similar, isLoading: similarLoading } = useSimilar(id, 14);
  const { data: myRatings } = useMyRatings();
  const { data: savedIds } = useWatchlistIds();
  const rate = useRateMovie();
  const toggleWatchlist = useToggleWatchlist();
  const toast = useToast();

  if (isLoading) return <PageSpinner label="Loading film" />;

  if (error || !movie) {
    return (
      <div className="mx-auto max-w-lg px-6 py-28 text-center">
        <Film className="mx-auto h-8 w-8 text-print-500" strokeWidth={1.4} />
        <h1 className="title-card mt-6 text-2xl text-print-50">Not in the collection</h1>
        <p className="mt-3 text-sm text-print-400">
          {error?.status === 404 ? 'That film is not in the catalogue.' : error?.message}
        </p>
        <button type="button" onClick={() => navigate(-1)} className="btn-secondary mt-8">
          <ArrowLeft className="h-4 w-4" />
          Go back
        </button>
      </div>
    );
  }

  const myRating = myRatings?.[String(movie.id)] ?? 0;
  const saved = savedIds?.has(Number(movie.id)) ?? false;

  return (
    <div>
      {/* ------------------------------------------------------------ plate */}
      <div className="relative">
        <div className="absolute inset-0 h-[64svh] overflow-hidden">
          {movie.backdrop_path ? (
            <img
              src={backdropUrl(movie.backdrop_path, 1280)}
              srcSet={backdropSrcSet(movie.backdrop_path)}
              sizes="100vw"
              alt=""
              loading="eager"
              fetchpriority="high"
              decoding="async"
              className="h-full w-full animate-slow-zoom object-cover"
            />
          ) : (
            <div className="h-full w-full bg-film-850" />
          )}
          <div className="absolute inset-0 bg-film-950/55" />
          <div className="absolute inset-0 bg-gradient-to-b from-film-950/70 via-film-950/80 to-film-950" />
          <div className="absolute inset-0 vignette" />
          <div className="grain absolute inset-0" />
          <CueMark />
        </div>

        <div className="relative mx-auto max-w-[1180px] px-6 pt-8 sm:px-10">
          <button type="button" onClick={() => navigate(-1)} className="btn-ghost mb-10 -ml-3">
            <ArrowLeft className="h-4 w-4" />
            Back
          </button>

          <div className="flex flex-col gap-10 pb-6 md:flex-row md:gap-12">
            <div className="w-40 shrink-0 sm:w-52 lg:w-60">
              <div className="border border-print-100/15 shadow-lift">
                <Poster
                  path={movie.poster_path}
                  alt={movie.title}
                  priority
                  maxWidth={500}
                  sizes="(max-width: 640px) 160px, 240px"
                  rounded="rounded-none"
                />
              </div>
              <p className="tech mt-3 text-center">{reelCode(movie.id)}</p>
            </div>

            <div className="min-w-0 flex-1">
              {movie.genres?.length > 0 && (
                <div className="mb-5 flex flex-wrap gap-1.5">
                  {movie.genres.map((genre) => (
                    <Link key={genre} to={`/discover?genre=${encodeURIComponent(genre)}`} className="chip">
                      {genre}
                    </Link>
                  ))}
                </div>
              )}

              <h1 className="title-card text-[clamp(2rem,5.5vw,4rem)] text-print-50">
                {movie.title}
              </h1>

              {movie.tagline && (
                <p className="mt-5 max-w-xl font-display text-lg font-light italic text-tungsten-400">
                  “{movie.tagline}”
                </p>
              )}

              <div className="mt-6 flex flex-wrap items-center gap-x-5 gap-y-2 font-mono text-2xs tabular-nums text-print-400">
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
                      {movie.vote_count > 0 && (
                        <span className="text-print-500">/ {compact(movie.vote_count)}</span>
                      )}
                    </span>
                  </>
                )}
                {movie.rating_count > 0 && (
                  <>
                    <span className="text-print-100/15">·</span>
                    <span>{compact(movie.rating_count)} MovieLens ratings</span>
                  </>
                )}
              </div>

              <div className="mt-9 flex flex-wrap items-center gap-3">
                {movie.trailer_key && (
                  <button type="button" onClick={() => setTrailerOpen(true)} className="btn-primary">
                    <Play className="h-4 w-4" style={{ fill: 'currentColor' }} />
                    Play trailer
                  </button>
                )}

                {isAuthenticated ? (
                  <button
                    type="button"
                    onClick={() => {
                      toggleWatchlist.mutate({ movieId: movie.id, saved });
                      toast.push({
                        kind: 'watchlist',
                        message: saved ? 'Removed from watchlist' : 'Saved to watchlist',
                        detail: movie.title,
                      });
                    }}
                    className="btn-secondary"
                  >
                    {saved ? <BookmarkCheck className="h-4 w-4 text-tungsten-500" /> : <Bookmark className="h-4 w-4" />}
                    {saved ? 'On your list' : 'Add to watchlist'}
                  </button>
                ) : (
                  <Link to="/signup" className="btn-secondary">
                    <Bookmark className="h-4 w-4" />
                    Sign up to save
                  </Link>
                )}
              </div>

              {isAuthenticated && (
                <div className="mt-7 inline-flex flex-wrap items-center gap-4 border border-print-100/12 px-4 py-3">
                  <span className="tech">Your rating</span>
                  <RatingStars
                    value={myRating}
                    size={20}
                    showValue
                    onChange={(next) => {
                      const value = next || 0.5;
                      rate.mutate({ movieId: movie.id, rating: value });
                      toast.push({
                        kind: 'rating',
                        message: `Rated ${value.toFixed(1)}`,
                        detail: movie.title,
                      });
                    }}
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ------------------------------------------------------------- body */}
      <div className="mx-auto max-w-[1180px] px-6 py-14 sm:px-10">
        <div className="grid gap-12 lg:grid-cols-3">
          <div className="lg:col-span-2">
            {movie.overview && (
              <section>
                <h2 className="slate-label mb-4">Synopsis</h2>
                <p className="max-w-2xl text-pretty text-[15px] leading-[1.75] text-print-200">
                  {movie.overview}
                </p>
              </section>
            )}

            <div className="mt-12">
              <CastRail billing={movie.billing} names={movie.cast} />
            </div>

            {movie.keywords?.length > 0 && (
              <section className="mt-12">
                <h2 className="slate-label mb-4">Themes</h2>
                <div className="flex flex-wrap gap-1.5">
                  {movie.keywords.slice(0, 18).map((keyword) => (
                    <span key={keyword} className="chip">{keyword}</span>
                  ))}
                </div>
              </section>
            )}

            {movie.tags?.length > 0 && (
              <section className="mt-12">
                <h2 className="slate-label mb-1">What viewers call it</h2>
                <p className="tech mb-4 normal-case">Tags contributed by MovieLens members</p>
                <div className="flex flex-wrap gap-1.5">
                  {movie.tags.map((tag) => (
                    <span key={tag} className="chip">{tag}</span>
                  ))}
                </div>
              </section>
            )}
          </div>

          <aside className="space-y-6">
            <SpecSheet
              title="Technical"
              rows={[
                { label: 'Runtime', value: timecode(movie.runtime) },
                {
                  label: 'Aspect',
                  value: inferAspectRatio(movie.year, movie.genres),
                  note: '≈',
                },
                { label: 'Language', value: languageName(movie.original_language) },
                { label: 'Released', value: movie.release_date },
                { label: 'Era', value: era(movie.year) },
                { label: 'Print', value: reelCode(movie.id) },
              ]}
            />

            <SpecSheet title="Credits">
              <div className="space-y-4 pt-1">
                {movie.director && (
                  <div>
                    <p className="tech mb-1">Directed by</p>
                    <p className="font-display text-sm uppercase tracking-slate text-print-100">
                      {movie.director}
                    </p>
                  </div>
                )}
                {movie.billing?.length > 0 && (
                  <div>
                    <p className="tech mb-1">Leading</p>
                    <p className="text-sm leading-relaxed text-print-200">
                      {movie.billing.slice(0, 3).map((m) => m.name).join(', ')}
                    </p>
                  </div>
                )}
              </div>

              {movie.imdb_id && (
                <a
                  href={`https://www.imdb.com/title/${movie.imdb_id}/`}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="btn-secondary mt-5 w-full px-4 py-2.5 text-2xs"
                >
                  View on IMDb
                </a>
              )}
            </SpecSheet>
          </aside>
        </div>

        {(similar?.length > 0 || similarLoading) && (
          <div className="mt-20">
            <MovieRow
              title="Double bill"
              subtitle="Blended from viewer overlap and shared themes"
              items={similar ?? []}
              loading={similarLoading}
            />
          </div>
        )}
      </div>

      <TrailerModal
        trailerKey={trailerOpen ? movie.trailer_key : null}
        title={movie.title}
        onClose={() => setTrailerOpen(false)}
      />
    </div>
  );
}
