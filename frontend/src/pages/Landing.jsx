import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion, useInView, useReducedMotion, useScroll, useTransform } from 'framer-motion';
import { ArrowRight, Github, Play } from 'lucide-react';
import Logo from '../components/Logo';
import MovieRow from '../components/MovieRow';
import Poster from '../components/Poster';
import CueMark from '../components/film/CueMark';
import Perforations from '../components/film/Perforations';
import SpecSheet from '../components/film/SpecSheet';
import { backdropSrcSet, backdropUrl } from '../lib/images';
import { compact, timecode } from '../lib/format';
import { useCatalogueStats, useHomeFeed, useModelMetrics } from '../lib/queries';
import { useAuth } from '../lib/auth';

const EASE = [0.22, 1, 0.36, 1];

function Reveal({ children, delay = 0, className = '' }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: '-12% 0px' });
  const reduce = useReducedMotion();

  return (
    <motion.div
      ref={ref}
      className={className}
      initial={reduce ? false : { opacity: 0, y: 24 }}
      animate={inView || reduce ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.7, ease: EASE, delay }}
    >
      {children}
    </motion.div>
  );
}

/* --------------------------------------------------------------------- hero */

/**
 * The opening: a letterboxed frame that plays like a projector starting up.
 *
 * The gate bars retract on load, the backdrop drifts in a slow push (the "Ken
 * Burns" move every title sequence uses), a cue mark burns in the top-right on a
 * long cycle, and grain sits over the whole thing. Cinematic framing carries the
 * page instead of a centred headline over a gradient.
 */
function Hero({ films }) {
  const reduce = useReducedMotion();
  const ref = useRef(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start start', 'end start'] });
  const y = useTransform(scrollYProgress, [0, 1], [0, reduce ? 0 : 110]);
  const fade = useTransform(scrollYProgress, [0, 0.8], [1, reduce ? 1 : 0]);

  // Cycle the backdrop slowly, like a trailer reel.
  const [index, setIndex] = useState(0);
  const featured = films[index % Math.max(films.length, 1)];

  useEffect(() => {
    if (films.length < 2 || reduce) return undefined;
    const timer = setInterval(() => setIndex((current) => current + 1), 9000);
    return () => clearInterval(timer);
  }, [films.length, reduce]);

  return (
    <section ref={ref} className="relative min-h-[100svh] overflow-hidden">
      <motion.div style={{ y, opacity: fade }} className="absolute inset-0">
        {featured?.backdrop_path && (
          <motion.img
            key={featured.id}
            src={backdropUrl(featured.backdrop_path, 1280)}
            srcSet={backdropSrcSet(featured.backdrop_path)}
            sizes="100vw"
            alt=""
            loading="eager"
            fetchpriority="high"
            decoding="async"
            initial={{ opacity: 0, scale: 1.1 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ opacity: { duration: 1.4 }, scale: { duration: 14, ease: 'linear' } }}
            className="absolute inset-0 h-full w-full object-cover"
          />
        )}

        {/* Grade the plate down so type stays legible over any artwork. */}
        <div className="absolute inset-0 bg-film-950/62" />
        <div className="absolute inset-0 bg-gradient-to-t from-film-950 via-film-950/55 to-film-950/70" />
        <div className="absolute inset-0 vignette" />
      </motion.div>

      {/* The gate: letterbox bars that retract as the projector opens. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 z-30 h-[12vh] origin-top animate-gate-open bg-film-950"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 bottom-0 z-30 h-[12vh] origin-bottom animate-gate-open bg-film-950"
      />

      <div className="grain absolute inset-0 z-10" />
      <CueMark />

      <div className="relative z-20 mx-auto flex min-h-[100svh] w-full max-w-[1500px] flex-col justify-between px-6 pb-10 pt-28 sm:px-10">
        <div className="max-w-4xl">
          <motion.p
            initial={reduce ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.9, duration: 0.8 }}
            className="slate-label mb-7"
          >
            Reel 01 · Feature Presentation
          </motion.p>

          <motion.h1
            initial={reduce ? false : { opacity: 0, y: 26 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 1.0, duration: 0.9, ease: EASE }}
            className="title-card text-[clamp(2.75rem,8.5vw,7.5rem)] text-print-50"
          >
            Every film
            <br />
            <span className="text-tungsten-500">worth your</span>
            <br />
            evening
          </motion.h1>

          <motion.p
            initial={reduce ? false : { opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 1.2, duration: 0.9, ease: EASE }}
            className="mt-8 max-w-lg text-pretty text-base leading-relaxed text-print-300 sm:text-lg"
          >
            Rate ten films. A model trained on 33 million ratings finds the rest —
            and names the films of yours that led it there.
          </motion.p>

          <motion.div
            initial={reduce ? false : { opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 1.35, duration: 0.9, ease: EASE }}
            className="mt-10 flex flex-col gap-3 sm:flex-row"
          >
            <Link to="/signup" className="btn-primary">
              <Play className="h-4 w-4" style={{ fill: 'currentColor' }} />
              Begin
            </Link>
            <Link to="/discover" className="btn-secondary">
              Browse the catalogue
            </Link>
          </motion.div>
        </div>

        {/* Now-showing strip along the bottom of the frame. */}
        <motion.div
          initial={reduce ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.6, duration: 1 }}
          className="hidden items-end justify-between gap-6 lg:flex"
        >
          <div className="flex items-center gap-4">
            <span className="tech whitespace-nowrap">Now showing</span>
            <span className="h-px w-16 bg-print-100/20" />
            <span className="font-display text-sm uppercase tracking-slate text-print-200">
              {featured?.title}
            </span>
            {featured?.year && (
              <span className="font-mono text-2xs tabular-nums text-print-500">
                {featured.year}
              </span>
            )}
          </div>

          <div className="flex items-center gap-1.5">
            {films.slice(0, 8).map((film, position) => (
              <button
                key={film.id}
                type="button"
                onClick={() => setIndex(position)}
                aria-label={`Show ${film.title}`}
                className={`h-[3px] transition-all duration-500 ${
                  position === index % Math.max(films.length, 1)
                    ? 'w-10 bg-tungsten-500'
                    : 'w-5 bg-print-100/25 hover:bg-print-100/50'
                }`}
              />
            ))}
          </div>
        </motion.div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ filmstrip */

/** A marquee of posters mounted in a 35mm strip, perforations and all. */
function FilmStrip({ films }) {
  const reduce = useReducedMotion();
  const strip = useMemo(() => [...films.slice(0, 16), ...films.slice(0, 16)], [films]);
  if (films.length === 0) return null;

  return (
    <section className="relative overflow-hidden border-y border-print-100/10 bg-film-900 py-0">
      <Perforations />

      <div className="relative overflow-hidden py-5">
        <div
          className="flex w-max gap-3 px-3"
          style={
            reduce ? undefined : { animation: 'strip-travel 62s linear infinite' }
          }
        >
          {strip.map((film, position) => (
            <Link
              key={`${film.id}-${position}`}
              to={`/movie/${film.id}`}
              className="group relative w-[108px] shrink-0 border border-print-100/10 transition-colors hover:border-tungsten-500"
            >
              <Poster
                path={film.poster_path}
                alt={film.title}
                maxWidth={185}
                sizes="108px"
                rounded="rounded-none"
              />
              <span className="pointer-events-none absolute inset-0 bg-film-950/45 transition-opacity group-hover:opacity-0" />
            </Link>
          ))}
        </div>
      </div>

      <Perforations />

      <style>{`
        @keyframes strip-travel {
          from { transform: translateX(0); }
          to   { transform: translateX(-50%); }
        }
      `}</style>
    </section>
  );
}

/* -------------------------------------------------------------- the programme */

/**
 * How it works, set as a programme of four movements.
 *
 * Asymmetric: the number and title sit left, the explanation right, with a rule
 * between them. Editorial layout of this kind is what film publications use and
 * it is the opposite of a three-up card grid of icons.
 */
function Programme() {
  const movements = [
    {
      number: 'I',
      title: 'Rate what you have seen',
      body:
        'Ten films is enough to place you. No questionnaire, no genre checkboxes. A film you disliked is as informative as one you loved, which is why the scale runs both ways.',
    },
    {
      number: 'II',
      title: 'Two models, read together',
      body:
        'A latent factor model finds the people whose taste matches yours. A neighbourhood model finds the films that sit closest to the ones you rated highly. Where a release is too new for either, content similarity carries it.',
    },
    {
      number: 'III',
      title: 'Re-ranked for range',
      body:
        'Pure relevance returns ten variations of one film. A diversity pass gives back a little accuracy to buy a list actually worth reading, and a novelty control lets you push past the canon whenever you want.',
    },
    {
      number: 'IV',
      title: 'Told why',
      body:
        'Every recommendation names the films in your own history that moved it up the ranking, with the weight each contributed — read out of the model, not reverse-engineered afterwards.',
    },
  ];

  return (
    <section className="mx-auto max-w-[1100px] px-6 py-24 sm:px-10 sm:py-32">
      <Reveal>
        <p className="slate-label mb-4">The programme</p>
        <h2 className="title-card max-w-2xl text-[clamp(1.85rem,4.4vw,3.25rem)] text-print-50">
          Four movements
        </h2>
      </Reveal>

      <div className="mt-16">
        {movements.map((movement, index) => (
          <Reveal key={movement.number} delay={index * 0.05}>
            <div className="group grid gap-6 border-t border-print-100/10 py-10 md:grid-cols-12 md:gap-10">
              <div className="md:col-span-1">
                <span className="font-display text-2xl font-light text-tungsten-500">
                  {movement.number}
                </span>
              </div>
              <div className="md:col-span-4">
                <h3 className="font-display text-xl font-medium uppercase tracking-slate text-print-50">
                  {movement.title}
                </h3>
              </div>
              <div className="md:col-span-7">
                <p className="text-pretty leading-relaxed text-print-300">{movement.body}</p>
              </div>
            </div>
          </Reveal>
        ))}
        <div className="border-t border-print-100/10" />
      </div>
    </section>
  );
}

/* ----------------------------------------------------------------- spec sheet */

/**
 * The evaluation report, set as a technical specification.
 *
 * This is the one section where the film conceit and the substance line up
 * exactly: these *are* technical specifications, and a spec sheet is the honest
 * way to show them — including the baseline, which is the number that makes the
 * rest meaningful.
 */
function TechnicalSpecs({ metrics, stats }) {
  const derived = useMemo(() => {
    const hybrid = metrics?.models?.hybrid;
    const base = metrics?.models?.popularity;
    if (!hybrid || !base) return null;
    return { hybrid, base, protocol: metrics.protocol, hyper: metrics.hyperparameters };
  }, [metrics]);

  return (
    <section className="border-y border-print-100/10 bg-film-900/50">
      <div className="mx-auto max-w-[1100px] px-6 py-24 sm:px-10 sm:py-32">
        <Reveal>
          <p className="slate-label mb-4">Technical specifications</p>
          <h2 className="title-card max-w-3xl text-[clamp(1.85rem,4.4vw,3.25rem)] text-print-50">
            Measured, not claimed
          </h2>
          <p className="mt-6 max-w-xl text-pretty leading-relaxed text-print-300">
            Test users are withheld from training entirely and scored through the same
            cold-start path a new account takes. Histories are split by time, and every
            unseen title in the catalogue competes — no sampled negatives.
          </p>
        </Reveal>

        {derived ? (
          <>
            <div className="mt-14 grid gap-px border border-print-100/10 bg-print-100/10 sm:grid-cols-2 lg:grid-cols-4">
              {[
                ['Hit rate @10', derived.hybrid['hit_rate@10'], derived.base['hit_rate@10']],
                ['NDCG @10', derived.hybrid['ndcg@10'], derived.base['ndcg@10']],
                ['Recall @20', derived.hybrid['recall@20'], derived.base['recall@20']],
                ['Coverage', derived.hybrid.coverage, derived.base.coverage],
              ].map(([label, value, baseline], index) => (
                <Reveal key={label} delay={index * 0.06}>
                  <div className="h-full bg-film-900 p-7">
                    <p className="tech mb-4">{label}</p>
                    <p className="font-display text-[2.75rem] font-light leading-none tabular-nums text-print-50">
                      {(value * 100).toFixed(1)}
                      <span className="ml-1 text-xl text-print-500">%</span>
                    </p>
                    <p className="mt-3 font-mono text-2xs tabular-nums text-tungsten-500">
                      {(value / baseline).toFixed(2)}× baseline
                    </p>
                  </div>
                </Reveal>
              ))}
            </div>

            <div className="mt-6 grid gap-6 md:grid-cols-2">
              <Reveal delay={0.08}>
                <SpecSheet
                  title="Protocol"
                  rows={[
                    { label: 'Method', value: 'Strong generalisation' },
                    { label: 'Test users', value: compact(derived.protocol.evaluation_users) },
                    { label: 'Candidates', value: compact(derived.protocol.catalogue_items) },
                    { label: 'Interactions', value: compact(derived.protocol.training_interactions) },
                    { label: 'Negatives', value: 'None sampled' },
                  ]}
                />
              </Reveal>

              <Reveal delay={0.14}>
                <SpecSheet
                  title="Model"
                  rows={[
                    { label: 'Latent factors', value: derived.hyper?.factors },
                    { label: 'Solver', value: 'Batched CG' },
                    { label: 'Neighbours', value: derived.hyper?.knn_top_k },
                    { label: 'Catalogue', value: compact(stats?.with_posters), note: 'titles' },
                    { label: 'Ranking AUC', value: `${(derived.hybrid.auc * 100).toFixed(1)}%`, accent: true },
                  ]}
                />
              </Reveal>
            </div>

            <Reveal delay={0.2}>
              <p className="mx-auto mt-10 max-w-2xl text-pretty text-center font-mono text-2xs leading-relaxed text-print-500">
                On honesty: ranking AUC clears 90% for almost anything on a catalogue
                this size — the popularity baseline manages{' '}
                <span className="text-print-300">
                  {(derived.base.auc * 100).toFixed(1)}%
                </span>
                . Hit rate and NDCG are the figures that separate a recommender from a
                bestseller list, which is why the baseline sits beside every one of them.
              </p>
            </Reveal>
          </>
        ) : (
          <Reveal>
            <p className="mt-14 font-mono text-sm text-print-500">
              Evaluation report unavailable — run the training pipeline.
            </p>
          </Reveal>
        )}
      </div>
    </section>
  );
}

/* --------------------------------------------------------------- selected row */

function Selection({ feed, loading }) {
  const row = feed?.rows?.find((item) => item.key === 'acclaimed') ?? feed?.rows?.[0];

  return (
    <section className="mx-auto max-w-[1500px] px-6 py-24 sm:px-10">
      <Reveal>
        <p className="slate-label mb-4">From the collection</p>
        <h2 className="title-card mb-12 text-[clamp(1.85rem,4.4vw,3.25rem)] text-print-50">
          Everything here is real
        </h2>
      </Reveal>
      <Reveal delay={0.08}>
        <MovieRow
          title={row?.title ?? 'Critically acclaimed'}
          subtitle={row?.subtitle}
          items={row?.items ?? []}
          loading={loading}
          spined
        />
      </Reveal>
    </section>
  );
}

/* ---------------------------------------------------------------- end credits */

function EndCard() {
  return (
    <section className="relative overflow-hidden border-t border-print-100/10 py-28 text-center sm:py-36">
      <div className="pointer-events-none absolute left-1/2 top-1/2 h-[30rem] w-[30rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-tungsten-500/10 blur-[130px]" />
      <Reveal className="relative mx-auto max-w-xl px-6">
        <p className="title-card text-[clamp(2.5rem,7vw,5rem)] text-print-50">Fin</p>
        <p className="mx-auto mt-7 max-w-sm text-pretty leading-relaxed text-print-300">
          Ten ratings and you never scroll a catalogue again. Free, no card, and your
          ratings stay yours.
        </p>
        <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Link to="/signup" className="btn-primary">
            Begin
            <ArrowRight className="h-4 w-4" />
          </Link>
          <Link to="/login" className="btn-secondary">
            Sign in
          </Link>
        </div>
      </Reveal>
    </section>
  );
}

function Footer({ stats }) {
  return (
    <footer className="border-t border-print-100/10 bg-film-900/50">
      <div className="mx-auto max-w-[1500px] px-6 py-12 sm:px-10">
        <div className="flex flex-col gap-8 md:flex-row md:items-start md:justify-between">
          <div>
            <Logo size={26} />
            <p className="tech mt-4 normal-case">
              {compact(stats?.with_posters) ?? '—'} titles · {compact(stats?.total_ratings_modelled) ?? '—'} ratings modelled
            </p>
          </div>

          <div className="max-w-md">
            <p className="text-pretty text-xs leading-relaxed text-print-500">
              Ratings and tags from the{' '}
              <a
                href="https://grouplens.org/datasets/movielens/"
                target="_blank"
                rel="noreferrer noopener"
                className="text-print-300 underline decoration-print-100/25 underline-offset-2 hover:text-tungsten-400"
              >
                MovieLens
              </a>{' '}
              dataset. Metadata, artwork and trailers from{' '}
              <a
                href="https://www.themoviedb.org/"
                target="_blank"
                rel="noreferrer noopener"
                className="text-print-300 underline decoration-print-100/25 underline-offset-2 hover:text-tungsten-400"
              >
                TMDB
              </a>
              . This product uses the TMDB API but is not endorsed or certified by TMDB.
            </p>
          </div>

          <a
            href="https://github.com/aryadhotre/MOVICO"
            target="_blank"
            rel="noreferrer noopener"
            className="btn-secondary shrink-0 px-4 py-2 text-2xs"
          >
            <Github className="h-3.5 w-3.5" />
            Source
          </a>
        </div>
      </div>
    </footer>
  );
}

/* --------------------------------------------------------------------- page */

export default function Landing() {
  const { isAuthenticated } = useAuth();
  const { data: feed, isLoading } = useHomeFeed();
  const { data: stats } = useCatalogueStats();
  const { data: metrics } = useModelMetrics();

  const heroFilms = useMemo(
    () => (feed?.hero ?? []).filter((film) => film.backdrop_path),
    [feed],
  );

  const stripFilms = useMemo(() => {
    const pool = [];
    feed?.rows?.forEach((row) => pool.push(...(row.items ?? [])));
    const seen = new Set();
    return pool.filter((film) => {
      if (!film.poster_path || seen.has(film.id)) return false;
      seen.add(film.id);
      return true;
    });
  }, [feed]);

  return (
    <div className="min-h-screen">
      <header className="fixed inset-x-0 top-0 z-50 border-b border-print-100/[0.07] bg-film-950/70 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[1500px] items-center justify-between px-6 py-4 sm:px-10">
          <Link to="/" aria-label="MOVICO home">
            <Logo size={25} />
          </Link>

          <nav className="flex items-center gap-2">
            <Link
              to="/discover"
              className="hidden font-display text-2xs uppercase tracking-slate text-print-300 transition-colors hover:text-tungsten-400 sm:block sm:px-4"
            >
              Catalogue
            </Link>
            {isAuthenticated ? (
              <Link to="/app" className="btn-primary px-5 py-2.5 text-2xs">
                Enter
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            ) : (
              <>
                <Link
                  to="/login"
                  className="font-display text-2xs uppercase tracking-slate text-print-300 transition-colors hover:text-tungsten-400 sm:px-4"
                >
                  Sign in
                </Link>
                <Link to="/signup" className="btn-primary px-5 py-2.5 text-2xs">
                  Begin
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>

      <Hero films={heroFilms} />
      <FilmStrip films={stripFilms} />
      <Programme />
      <TechnicalSpecs metrics={metrics} stats={stats} />
      <Selection feed={feed} loading={isLoading} />
      <EndCard />
      <Footer stats={stats} />
    </div>
  );
}
