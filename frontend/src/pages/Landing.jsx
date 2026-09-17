import { useMemo, useRef } from 'react';
import { Link } from 'react-router-dom';
import { motion, useInView, useReducedMotion, useScroll, useTransform } from 'framer-motion';
import {
  ArrowRight,
  Boxes,
  Clock3,
  Github,
  Layers,
  MessageSquareQuote,
  Search,
  Shuffle,
  Sparkles,
  Star,
  TrendingUp,
} from 'lucide-react';
import Logo from '../components/Logo';
import MovieRow from '../components/MovieRow';
import PosterWall from '../components/PosterWall';
import { useCatalogueStats, useHomeFeed, useModelMetrics } from '../lib/queries';
import { useAuth } from '../lib/auth';

const EASE = [0.22, 1, 0.36, 1];

function compact(value) {
  if (value === null || value === undefined) return '—';
  const number = Number(value);
  if (Number.isNaN(number)) return '—';
  if (number >= 1_000_000) return `${(number / 1_000_000).toFixed(number >= 10_000_000 ? 0 : 1)}M`;
  if (number >= 1_000) return `${(number / 1_000).toFixed(number >= 10_000 ? 0 : 1)}k`;
  return number.toLocaleString();
}

/** Fades a section in the first time it scrolls into view. */
function Reveal({ children, delay = 0, className = '' }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: '-12% 0px' });
  const reduce = useReducedMotion();

  return (
    <motion.div
      ref={ref}
      className={className}
      initial={reduce ? false : { opacity: 0, y: 26 }}
      animate={inView || reduce ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.65, ease: EASE, delay }}
    >
      {children}
    </motion.div>
  );
}

function SectionHeading({ eyebrow, title, description, className = '' }) {
  return (
    <div className={`mx-auto max-w-2xl text-center ${className}`}>
      {eyebrow && <p className="eyebrow mb-3">{eyebrow}</p>}
      <h2 className="text-balance text-3xl font-semibold tracking-tightest text-white sm:text-4xl">
        {title}
      </h2>
      {description && (
        <p className="mt-4 text-pretty text-[15px] leading-relaxed text-white/50">{description}</p>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------- sections */

function Hero({ wallMovies, stats }) {
  const ref = useRef(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start start', 'end start'] });
  // Subtle parallax: the copy lifts slightly faster than the page scrolls.
  const y = useTransform(scrollYProgress, [0, 1], [0, reduce ? 0 : -70]);
  const opacity = useTransform(scrollYProgress, [0, 0.75], [1, reduce ? 1 : 0]);

  const pills = [
    { icon: Boxes, label: `${compact(stats?.with_posters)} films` },
    { icon: TrendingUp, label: `${compact(stats?.total_ratings_modelled)} ratings modelled` },
    { icon: Clock3, label: 'Updated weekly from TMDB' },
  ];

  return (
    <section ref={ref} className="noise relative flex min-h-[94svh] items-center overflow-hidden">
      <PosterWall movies={wallMovies} />

      <motion.div
        style={{ y, opacity }}
        className="relative z-10 mx-auto w-full max-w-4xl px-6 py-24 text-center"
      >
        <motion.div
          initial={reduce ? false : { opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: EASE }}
          className="mb-8 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.05] px-3.5 py-1.5 text-2xs font-medium text-white/65 backdrop-blur-md"
        >
          <span className="relative flex h-1.5 w-1.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-mint-500 opacity-60" />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-mint-500" />
          </span>
          Hybrid recommender · trained on 33M ratings
        </motion.div>

        <motion.h1
          initial={reduce ? false : { opacity: 0, y: 22 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: EASE, delay: 0.06 }}
          className="text-balance text-5xl font-semibold leading-[0.98] tracking-tightest text-white sm:text-6xl lg:text-7xl"
        >
          Stop scrolling.
          <br />
          <span className="font-display text-[1.08em] font-normal italic text-gradient">
            Start watching.
          </span>
        </motion.h1>

        <motion.p
          initial={reduce ? false : { opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: EASE, delay: 0.14 }}
          className="mx-auto mt-6 max-w-xl text-pretty text-base leading-relaxed text-white/55 sm:text-lg"
        >
          MOVICO learns what you actually like from a handful of ratings, then finds
          the films worth your evening — and tells you exactly why it picked each one.
        </motion.p>

        <motion.div
          initial={reduce ? false : { opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: EASE, delay: 0.22 }}
          className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row"
        >
          <Link to="/signup" className="btn-primary w-full px-7 py-3 text-[15px] sm:w-auto">
            Build my taste profile
            <ArrowRight className="h-4 w-4" />
          </Link>
          <Link to="/discover" className="btn-secondary w-full px-7 py-3 text-[15px] sm:w-auto">
            Browse the catalogue
          </Link>
        </motion.div>

        <motion.div
          initial={reduce ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.9, ease: EASE, delay: 0.34 }}
          className="mt-12 flex flex-wrap items-center justify-center gap-x-6 gap-y-3"
        >
          {pills.map(({ icon: Icon, label }) => (
            <span key={label} className="flex items-center gap-2 text-2xs font-medium text-white/40">
              <Icon className="h-3.5 w-3.5" strokeWidth={2} />
              {label}
            </span>
          ))}
        </motion.div>
      </motion.div>
    </section>
  );
}

function HowItWorks() {
  const steps = [
    {
      icon: Star,
      title: 'Rate a few films',
      body:
        'Ten ratings is enough to place you in the taste space. No questionnaire, no genre checkboxes you will regret.',
    },
    {
      icon: Layers,
      title: 'Two models, one ranking',
      body:
        'A latent factor model finds people who share your taste. A neighbourhood model finds films like the ones you loved. Content similarity covers releases too new for either.',
    },
    {
      icon: Shuffle,
      title: 'Re-ranked for range',
      body:
        'Raw relevance returns ten near-identical films. A diversity pass trades a little of it for a list actually worth reading.',
    },
    {
      icon: MessageSquareQuote,
      title: 'Told why',
      body:
        'Every pick names the films in your profile that drove it, read straight out of the model — not a plausible guess after the fact.',
    },
  ];

  return (
    <section className="relative mx-auto max-w-6xl px-6 py-24 sm:py-32">
      <Reveal>
        <SectionHeading
          eyebrow="How it works"
          title="A recommender that shows its reasoning"
          description="Most recommendation feeds are a black box. This one is four explicit stages, and you can see the output of each."
        />
      </Reveal>

      <div className="mt-14 grid gap-4 sm:grid-cols-2">
        {steps.map(({ icon: Icon, title, body }, index) => (
          <Reveal key={title} delay={index * 0.07}>
            <div className="card-hairline ring-gradient h-full p-6 transition-transform duration-300 ease-smooth hover:-translate-y-1">
              <div className="mb-4 flex items-center gap-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-soft text-violet-400 ring-1 ring-inset ring-white/10">
                  <Icon className="h-[18px] w-[18px]" strokeWidth={2} />
                </span>
                <span className="text-2xs font-semibold tabular-nums text-white/25">
                  0{index + 1}
                </span>
              </div>
              <h3 className="text-base font-semibold text-white">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-white/50">{body}</p>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}

function Metrics({ metrics, stats }) {
  const derived = useMemo(() => {
    const hybrid = metrics?.models?.hybrid;
    const baseline = metrics?.models?.popularity;
    if (!hybrid || !baseline) return null;

    const hr = hybrid['hit_rate@10'];
    const baseHr = baseline['hit_rate@10'];
    const ndcg = hybrid['ndcg@10'];
    const baseNdcg = baseline['ndcg@10'];

    return {
      hr: (hr * 100).toFixed(1),
      hrLift: baseHr ? (hr / baseHr).toFixed(2) : null,
      ndcg: (ndcg * 100).toFixed(1),
      ndcgLift: baseNdcg ? (ndcg / baseNdcg).toFixed(2) : null,
      auc: (hybrid.auc * 100).toFixed(1),
      recall: (hybrid['recall@20'] * 100).toFixed(1),
      users: hybrid.evaluated_users,
      items: metrics?.protocol?.catalogue_items,
      interactions: metrics?.protocol?.training_interactions,
      factors: metrics?.hyperparameters?.factors,
    };
  }, [metrics]);

  return (
    <section className="relative border-y border-white/[0.06] bg-ink-900/40 py-24 sm:py-32">
      <div className="mx-auto max-w-6xl px-6">
        <Reveal>
          <SectionHeading
            eyebrow="Measured, not claimed"
            title="Evaluated the strict way"
            description="Test users are held out of training entirely and scored through the same cold-start path a new signup takes. Their history is split by time, and every unseen title in the catalogue competes — no sampled negatives."
          />
        </Reveal>

        {derived ? (
          <>
            <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {[
                {
                  value: `${derived.hr}%`,
                  label: 'Hit rate @10',
                  note: derived.hrLift ? `${derived.hrLift}× the popularity baseline` : null,
                },
                {
                  value: `${derived.ndcg}%`,
                  label: 'NDCG @10',
                  note: derived.ndcgLift ? `${derived.ndcgLift}× the baseline` : null,
                },
                {
                  value: `${derived.recall}%`,
                  label: 'Recall @20',
                  note: 'Of everything they went on to watch',
                },
                {
                  value: `${derived.auc}%`,
                  label: 'Ranking AUC',
                  note: 'Pairwise ordering across the catalogue',
                },
              ].map(({ value, label, note }, index) => (
                <Reveal key={label} delay={index * 0.06}>
                  <div className="card-hairline h-full p-6 text-center">
                    <p className="text-4xl font-semibold tabular-nums tracking-tightest text-gradient">
                      {value}
                    </p>
                    <p className="mt-2 text-sm font-medium text-white">{label}</p>
                    {note && <p className="mt-1.5 text-2xs leading-relaxed text-white/35">{note}</p>}
                  </div>
                </Reveal>
              ))}
            </div>

            <Reveal delay={0.1}>
              <div className="mt-6 grid gap-3 text-center sm:grid-cols-4">
                {[
                  ['Training interactions', compact(derived.interactions)],
                  ['Catalogue modelled', compact(derived.items)],
                  ['Latent factors', derived.factors ?? '—'],
                  ['Held-out test users', compact(derived.users)],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-xl border border-white/[0.06] px-4 py-3">
                    <p className="text-lg font-semibold tabular-nums text-white">{value}</p>
                    <p className="mt-0.5 text-2xs text-white/40">{label}</p>
                  </div>
                ))}
              </div>
            </Reveal>

            <Reveal delay={0.16}>
              <p className="mx-auto mt-8 max-w-2xl text-center text-2xs leading-relaxed text-white/30">
                A note on honesty: ranking AUC clears 90% for almost any model on a
                catalogue this size — the popularity baseline manages{' '}
                {(metrics.models.popularity.auc * 100).toFixed(1)}%. Hit rate and NDCG
                are the numbers that actually separate a recommender from a
                bestseller list, which is why the lift over baseline is shown beside them.
              </p>
            </Reveal>
          </>
        ) : (
          <Reveal>
            <div className="mx-auto mt-14 max-w-md rounded-2xl border border-white/[0.06] p-8 text-center">
              <p className="text-sm text-white/45">
                Model evaluation report is not available yet.
              </p>
              {stats?.total_movies ? (
                <p className="mt-2 text-2xs text-white/30">
                  Catalogue is live with {compact(stats.with_posters)} films.
                </p>
              ) : null}
            </div>
          </Reveal>
        )}
      </div>
    </section>
  );
}

function Features() {
  const features = [
    {
      icon: Sparkles,
      title: 'Explained recommendations',
      body: 'Each pick names the films from your profile that drove it, with the weight each contributed.',
    },
    {
      icon: Shuffle,
      title: 'Dials you control',
      body: 'Diversity and novelty are sliders, not a fixed opinion. Push toward the long tail whenever you want to.',
    },
    {
      icon: Search,
      title: 'Search that keeps up',
      body: 'Full-text search over titles, directors and cast, indexed so it answers while you are still typing.',
    },
    {
      icon: TrendingUp,
      title: 'Genuinely current',
      body: 'Releases land from TMDB continuously, so this year’s films are here — not just a frozen 2023 archive.',
    },
    {
      icon: Star,
      title: 'Your taste, visualised',
      body: 'Genre balance, rating spread and the decades you gravitate toward, drawn from your own history.',
    },
    {
      icon: Boxes,
      title: 'Cold start handled',
      body: 'A brand-new account gets real recommendations from the first ten ratings, no retraining required.',
    },
  ];

  return (
    <section className="mx-auto max-w-6xl px-6 py-24 sm:py-32">
      <Reveal>
        <SectionHeading eyebrow="What you get" title="Built like a product, not a notebook" />
      </Reveal>

      <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {features.map(({ icon: Icon, title, body }, index) => (
          <Reveal key={title} delay={(index % 3) * 0.06}>
            <div className="group h-full rounded-2xl border border-white/[0.06] bg-ink-900/40 p-6 transition-colors duration-300 hover:border-white/[0.14] hover:bg-ink-850/60">
              <Icon
                className="h-5 w-5 text-violet-400 transition-transform duration-300 group-hover:scale-110"
                strokeWidth={2}
              />
              <h3 className="mt-4 text-[15px] font-semibold text-white">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-white/45">{body}</p>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}

function CatalogueTaste({ feed, loading }) {
  const row = feed?.rows?.find((item) => item.key === 'trending') ?? feed?.rows?.[0];

  return (
    <section className="border-y border-white/[0.06] bg-ink-900/30 py-20">
      <div className="mx-auto max-w-[1500px] px-6">
        <Reveal>
          <SectionHeading
            eyebrow="Live catalogue"
            title="Everything below is real data"
            className="mb-12"
          />
        </Reveal>
        <Reveal delay={0.08}>
          <MovieRow
            title={row?.title ?? 'Trending this week'}
            subtitle={row?.subtitle}
            items={row?.items ?? []}
            loading={loading}
          />
        </Reveal>
      </div>
    </section>
  );
}

function FinalCta() {
  return (
    <section className="relative overflow-hidden py-28 sm:py-36">
      <div className="pointer-events-none absolute left-1/2 top-1/2 h-[34rem] w-[34rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-violet-600/18 blur-[120px]" />
      <Reveal className="relative mx-auto max-w-2xl px-6 text-center">
        <h2 className="text-balance text-4xl font-semibold tracking-tightest text-white sm:text-5xl">
          Ten ratings. Then never scroll again.
        </h2>
        <p className="mx-auto mt-5 max-w-lg text-pretty text-[15px] leading-relaxed text-white/50">
          Free, no card, and your ratings stay yours. The whole thing is open source.
        </p>
        <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Link to="/signup" className="btn-primary w-full px-7 py-3 text-[15px] sm:w-auto">
            Get started
            <ArrowRight className="h-4 w-4" />
          </Link>
          <Link to="/login" className="btn-secondary w-full px-7 py-3 text-[15px] sm:w-auto">
            I already have an account
          </Link>
        </div>
      </Reveal>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t border-white/[0.06] py-12">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-6 px-6 sm:flex-row">
        <Logo size={26} />
        <p className="text-center text-2xs text-white/35 sm:text-left">
          Ratings from the{' '}
          <a
            href="https://grouplens.org/datasets/movielens/"
            target="_blank"
            rel="noreferrer noopener"
            className="text-white/55 underline decoration-white/20 underline-offset-2 hover:text-white"
          >
            MovieLens
          </a>{' '}
          dataset · metadata and artwork from{' '}
          <a
            href="https://www.themoviedb.org/"
            target="_blank"
            rel="noreferrer noopener"
            className="text-white/55 underline decoration-white/20 underline-offset-2 hover:text-white"
          >
            TMDB
          </a>
          . Not endorsed by either.
        </p>
        <a
          href="https://github.com/aryadhotre/MOVICO"
          target="_blank"
          rel="noreferrer noopener"
          className="btn-secondary px-4 py-2 text-2xs"
        >
          <Github className="h-3.5 w-3.5" />
          Source
        </a>
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

  // One flat pool of artwork for the hero wall, drawn from every row.
  const wallMovies = useMemo(() => {
    const pool = [...(feed?.hero ?? [])];
    feed?.rows?.forEach((row) => pool.push(...(row.items ?? [])));
    const seen = new Set();
    return pool.filter((movie) => {
      if (seen.has(movie.id)) return false;
      seen.add(movie.id);
      return true;
    });
  }, [feed]);

  return (
    <div className="min-h-screen">
      <header className="fixed inset-x-0 top-0 z-50 border-b border-white/[0.05] bg-ink-950/60 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3.5">
          <Link to="/" aria-label="MOVICO home">
            <Logo size={27} />
          </Link>
          <nav className="flex items-center gap-2">
            <Link to="/discover" className="btn-ghost hidden text-sm sm:inline-flex">
              Browse
            </Link>
            {isAuthenticated ? (
              <Link to="/app" className="btn-primary px-5 py-2">
                Open app
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            ) : (
              <>
                <Link to="/login" className="btn-ghost text-sm">
                  Sign in
                </Link>
                <Link to="/signup" className="btn-primary px-5 py-2">
                  Get started
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>

      <Hero wallMovies={wallMovies} stats={stats} />
      <HowItWorks />
      <Metrics metrics={metrics} stats={stats} />
      <CatalogueTaste feed={feed} loading={isLoading} />
      <Features />
      <FinalCta />
      <Footer />
    </div>
  );
}
