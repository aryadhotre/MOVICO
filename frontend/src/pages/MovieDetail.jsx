import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import {
  ArrowLeft,
  Bookmark,
  BookmarkCheck,
  Clock3,
  Film,
  Play,
  Star,
  Users,
  X,
} from 'lucide-react';
import MovieRow from '../components/MovieRow';
import RatingStars from '../components/RatingStars';
import Poster from '../components/Poster';
import PageSpinner from '../components/PageSpinner';
import { backdropSrcSet, backdropUrl, youtubeEmbed } from '../lib/images';
import {
  useMovie,
  useMyRatings,
  useRateMovie,
  useSimilar,
  useToggleWatchlist,
  useWatchlistIds,
} from '../lib/queries';
import { useAuth } from '../lib/auth';

function formatRuntime(minutes) {
  if (!minutes) return null;
  const hours = Math.floor(minutes / 60);
  return hours ? `${hours}h ${minutes % 60}m` : `${minutes}m`;
}

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
          <div className="absolute inset-0 bg-ink-950/90 backdrop-blur-sm" onClick={onClose} />
          <motion.div
            className="relative w-full max-w-4xl overflow-hidden rounded-2xl bg-black shadow-lift"
            initial={{ scale: 0.96, y: 10 }}
            animate={{ scale: 1, y: 0 }}
            exit={{ scale: 0.98, opacity: 0 }}
            transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
          >
            <button
              type="button"
              onClick={onClose}
              aria-label="Close trailer"
              className="absolute right-3 top-3 z-10 btn-icon bg-ink-950/80"
            >
              <X className="h-4 w-4" />
            </button>
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

  if (isLoading) return <PageSpinner />;

  if (error || !movie) {
    return (
      <div className="mx-auto max-w-lg px-6 py-24 text-center">
        <Film className="mx-auto h-9 w-9 text-white/20" strokeWidth={1.5} />
        <h1 className="mt-4 text-xl font-semibold text-white">Film not found</h1>
        <p className="mt-2 text-sm text-white/45">
          {error?.status === 404 ? 'That film is not in the catalogue.' : error?.message}
        </p>
        <button type="button" onClick={() => navigate(-1)} className="btn-secondary mt-6 px-5 py-2.5">
          <ArrowLeft className="h-4 w-4" />
          Go back
        </button>
      </div>
    );
  }

  const myRating = myRatings?.[String(movie.id)] ?? 0;
  const saved = savedIds?.has(Number(movie.id)) ?? false;
  const runtime = formatRuntime(movie.runtime);

  return (
    <div>
      {/* ------------------------------------------------------------ backdrop */}
      <div className="relative">
        <div className="absolute inset-0 h-[58svh] overflow-hidden">
          {movie.backdrop_path ? (
            <img
              src={backdropUrl(movie.backdrop_path, 1280)}
              srcSet={backdropSrcSet(movie.backdrop_path)}
              sizes="100vw"
              alt=""
              loading="eager"
              fetchpriority="high"
              decoding="async"
              className="h-full w-full object-cover object-top"
            />
          ) : (
            <div className="h-full w-full bg-ink-850" />
          )}
          <div className="absolute inset-0 bg-gradient-to-b from-ink-950/55 via-ink-950/80 to-ink-950" />
        </div>

        <div className="relative mx-auto max-w-6xl px-5 pt-6 sm:px-6">
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="btn-secondary mb-8 px-4 py-2 text-sm"
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </button>

          <div className="flex flex-col gap-8 pb-4 sm:flex-row sm:gap-10">
            <div className="w-40 shrink-0 sm:w-56 lg:w-64">
              <div className="overflow-hidden rounded-2xl shadow-lift ring-1 ring-white/10">
                <Poster
                  path={movie.poster_path}
                  alt={movie.title}
                  priority
                  maxWidth={500}
                  sizes="(max-width: 640px) 160px, 256px"
                  rounded="rounded-none"
                />
              </div>
            </div>

            <div className="min-w-0 flex-1 pt-1">
              {movie.genres?.length > 0 && (
                <div className="mb-3 flex flex-wrap gap-1.5">
                  {movie.genres.map((genre) => (
                    <Link
                      key={genre}
                      to={`/discover?genre=${encodeURIComponent(genre)}`}
                      className="chip hover:border-white/25 hover:text-white"
                    >
                      {genre}
                    </Link>
                  ))}
                </div>
              )}

              <h1 className="text-balance text-3xl font-semibold leading-tight tracking-tightest text-white sm:text-4xl lg:text-5xl">
                {movie.title}
              </h1>

              {movie.tagline && (
                <p className="mt-3 font-display text-lg italic text-white/45">{movie.tagline}</p>
              )}

              <div className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-white/55">
                {movie.year && <span className="tabular-nums">{movie.year}</span>}
                {runtime && (
                  <span className="flex items-center gap-1.5">
                    <Clock3 className="h-3.5 w-3.5" />
                    {runtime}
                  </span>
                )}
                {movie.vote_average > 0 && (
                  <span className="flex items-center gap-1.5 text-amber-500">
                    <Star className="h-4 w-4" style={{ fill: 'currentColor' }} />
                    <span className="font-semibold tabular-nums">
                      {movie.vote_average.toFixed(1)}
                    </span>
                    {movie.vote_count > 0 && (
                      <span className="text-white/35">
                        ({movie.vote_count.toLocaleString()})
                      </span>
                    )}
                  </span>
                )}
                {movie.rating_count > 0 && (
                  <span className="flex items-center gap-1.5">
                    <Users className="h-3.5 w-3.5" />
                    {movie.rating_count.toLocaleString()} MovieLens ratings
                    {movie.rating_mean > 0 && (
                      <span className="text-white/35">· {movie.rating_mean.toFixed(2)} avg</span>
                    )}
                  </span>
                )}
              </div>

              <div className="mt-7 flex flex-wrap items-center gap-3">
                {movie.trailer_key && (
                  <button
                    type="button"
                    onClick={() => setTrailerOpen(true)}
                    className="btn-primary px-6 py-2.5"
                  >
                    <Play className="h-4 w-4" style={{ fill: 'currentColor' }} />
                    Watch trailer
                  </button>
                )}

                {isAuthenticated ? (
                  <button
                    type="button"
                    onClick={() => toggleWatchlist.mutate({ movieId: movie.id, saved })}
                    className="btn-secondary px-5 py-2.5"
                  >
                    {saved ? (
                      <BookmarkCheck className="h-4 w-4 text-violet-400" />
                    ) : (
                      <Bookmark className="h-4 w-4" />
                    )}
                    {saved ? 'In watchlist' : 'Add to watchlist'}
                  </button>
                ) : (
                  <Link to="/signup" className="btn-secondary px-5 py-2.5">
                    <Bookmark className="h-4 w-4" />
                    Sign up to save
                  </Link>
                )}
              </div>

              {isAuthenticated && (
                <div className="mt-6 inline-flex flex-wrap items-center gap-4 rounded-xl border border-white/[0.07] bg-white/[0.03] px-4 py-3">
                  <span className="text-2xs font-medium text-white/50">Your rating</span>
                  <RatingStars
                    value={myRating}
                    size={22}
                    showValue
                    onChange={(next) =>
                      rate.mutate({ movieId: movie.id, rating: next || 0.5 })
                    }
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* --------------------------------------------------------------- body */}
      <div className="mx-auto max-w-6xl px-5 py-12 sm:px-6">
        <div className="grid gap-10 lg:grid-cols-3">
          <div className="lg:col-span-2">
            {movie.overview && (
              <section>
                <h2 className="mb-3 text-lg font-semibold text-white">Synopsis</h2>
                <p className="text-pretty text-[15px] leading-relaxed text-white/60">
                  {movie.overview}
                </p>
              </section>
            )}

            {movie.keywords?.length > 0 && (
              <section className="mt-9">
                <h2 className="mb-3 text-lg font-semibold text-white">Themes</h2>
                <div className="flex flex-wrap gap-1.5">
                  {movie.keywords.slice(0, 16).map((keyword) => (
                    <span key={keyword} className="chip">
                      {keyword}
                    </span>
                  ))}
                </div>
              </section>
            )}

            {movie.tags?.length > 0 && (
              <section className="mt-9">
                <h2 className="mb-1.5 text-lg font-semibold text-white">What viewers call it</h2>
                <p className="mb-3 text-2xs text-white/35">
                  Tags contributed by MovieLens users
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {movie.tags.map((tag) => (
                    <span key={tag} className="chip">
                      {tag}
                    </span>
                  ))}
                </div>
              </section>
            )}
          </div>

          <aside className="space-y-6">
            <div className="card-hairline p-5">
              <h2 className="mb-4 text-sm font-semibold text-white">Credits</h2>
              <dl className="space-y-3 text-sm">
                {movie.director && (
                  <div>
                    <dt className="text-2xs text-white/40">Director</dt>
                    <dd className="mt-0.5 text-white/80">{movie.director}</dd>
                  </div>
                )}
                {movie.cast?.length > 0 && (
                  <div>
                    <dt className="text-2xs text-white/40">Cast</dt>
                    <dd className="mt-0.5 leading-relaxed text-white/80">
                      {movie.cast.slice(0, 8).join(', ')}
                    </dd>
                  </div>
                )}
                {movie.release_date && (
                  <div>
                    <dt className="text-2xs text-white/40">Released</dt>
                    <dd className="mt-0.5 tabular-nums text-white/80">{movie.release_date}</dd>
                  </div>
                )}
                {movie.original_language && (
                  <div>
                    <dt className="text-2xs text-white/40">Original language</dt>
                    <dd className="mt-0.5 uppercase text-white/80">{movie.original_language}</dd>
                  </div>
                )}
              </dl>

              {movie.imdb_id && (
                <a
                  href={`https://www.imdb.com/title/${movie.imdb_id}/`}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="btn-secondary mt-5 w-full px-4 py-2 text-2xs"
                >
                  View on IMDb
                </a>
              )}
            </div>
          </aside>
        </div>

        {(similar?.length > 0 || similarLoading) && (
          <div className="mt-14">
            <MovieRow
              title="More like this"
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
