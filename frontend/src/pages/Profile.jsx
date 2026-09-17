import { Link } from 'react-router-dom';
import { Bookmark, Star, TrendingUp, User as UserIcon } from 'lucide-react';
import EmptyState from '../components/EmptyState';
import SpecSheet from '../components/film/SpecSheet';
import { useTasteStats } from '../lib/queries';
import { useAuth } from '../lib/auth';

/**
 * Genre affinity as horizontal bars.
 *
 * Plain divs rather than a charting library: the shapes are trivial, and pulling
 * in a chart runtime for four bar rows would cost more bundle than the whole page.
 * Normalised against the largest value so the longest bar always fills the track.
 */
function BarList({ items, total }) {
  const max = Math.max(...items.map((item) => item.movie_count), 1);

  return (
    <ul className="space-y-4">
      {items.map(({ name, movie_count: count }) => (
        <li key={name}>
          <div className="mb-2 flex items-baseline justify-between gap-3">
            <span className="truncate font-display text-2xs uppercase tracking-slate text-print-200">
              {name}
            </span>
            <span className="shrink-0 font-mono text-2xs tabular-nums text-print-500">
              {count}
              {total ? ` · ${Math.round((count / total) * 100)}%` : ''}
            </span>
          </div>
          <div className="h-[3px] bg-print-100/10">
            <div
              className="h-full bg-tungsten-500 transition-[width] duration-700 ease-reel"
              style={{ width: `${(count / max) * 100}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}

/** Rating distribution, drawn like a levels meter. */
function RatingHistogram({ distribution }) {
  const buckets = ['0.5', '1', '1.5', '2', '2.5', '3', '3.5', '4', '4.5', '5'];
  const max = Math.max(...buckets.map((key) => distribution[key] ?? 0), 1);

  return (
    <div className="flex h-40 items-end gap-1.5">
      {buckets.map((key) => {
        const count = distribution[key] ?? 0;
        return (
          <div key={key} className="flex flex-1 flex-col items-center gap-2">
            <span className="font-mono text-[10px] tabular-nums text-print-500">
              {count || ''}
            </span>
            <div
              className="w-full bg-tungsten-500 transition-[height] duration-700 ease-reel"
              // A 2px floor keeps empty buckets legible as a baseline.
              style={{ height: `${Math.max((count / max) * 100, count ? 6 : 2)}%` }}
              title={`${count} rated ${key}`}
            />
            <span className="font-mono text-[10px] tabular-nums text-print-500">{key}</span>
          </div>
        );
      })}
    </div>
  );
}

function StatTile({ icon: Icon, label, value, hint }) {
  return (
    <div className="border border-print-100/10 bg-film-900/60 p-6">
      <Icon className="h-4 w-4 text-tungsten-500" strokeWidth={1.8} />
      <p className="mt-4 font-display text-[2rem] font-light leading-none tabular-nums text-print-50">
        {value}
      </p>
      <p className="tech mt-2">{label}</p>
      {hint && <p className="mt-1.5 font-mono text-[10px] text-print-500">{hint}</p>}
    </div>
  );
}

export default function Profile() {
  const { user } = useAuth();
  const { data: stats, isLoading } = useTasteStats();

  return (
    <div className="mx-auto max-w-5xl px-5 py-8 sm:px-8">
      <header className="mb-12 flex flex-wrap items-center gap-6 border-b border-print-100/10 pb-8">
        <div className="flex h-16 w-16 shrink-0 items-center justify-center border border-tungsten-500/50 font-display text-xl uppercase tracking-slate text-tungsten-400">
          {user?.username?.slice(0, 2)}
        </div>
        <div className="min-w-0">
          <p className="slate-label mb-2">Member</p>
          <h1 className="title-card truncate text-2xl text-print-50">{user?.username}</h1>
          <p className="mt-2 font-mono text-2xs text-print-500">
            {user?.email}
            {user?.created_at && ` · joined ${new Date(user.created_at).toLocaleDateString()}`}
          </p>
        </div>
      </header>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-3">
          {Array.from({ length: 3 }, (_, index) => (
            <div key={index} className="skeleton h-36" />
          ))}
        </div>
      ) : !stats || stats.ratings_count === 0 ? (
        <EmptyState
          icon={UserIcon}
          title="No taste profile yet"
          description="Rate a handful of films and this page fills in with your genre balance, rating spread and the eras you lean toward."
          action={{ to: '/onboarding', label: 'Start rating' }}
        />
      ) : (
        <div className="space-y-8">
          <div className="grid gap-4 sm:grid-cols-3">
            <StatTile icon={Star} label="Films rated" value={stats.ratings_count} />
            <StatTile
              icon={TrendingUp}
              label="Average rating"
              value={stats.average_rating.toFixed(2)}
              hint={
                stats.average_rating > 3.8
                  ? 'You rate generously'
                  : stats.average_rating < 3.2
                    ? 'A tough critic'
                    : 'Well calibrated'
              }
            />
            <StatTile icon={Bookmark} label="On your watchlist" value={stats.watchlist_count} />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <section className="panel p-6">
              <h2 className="slate-label mb-1">Genres you gravitate to</h2>
              <p className="tech mb-6 normal-case">Counted from films you rated 3.5 or higher</p>
              {stats.top_genres?.length > 0 ? (
                <BarList items={stats.top_genres} total={stats.ratings_count} />
              ) : (
                <p className="text-sm text-print-400">
                  Rate a few films positively to see this.
                </p>
              )}
            </section>

            <section className="panel p-6">
              <h2 className="slate-label mb-1">How you rate</h2>
              <p className="tech mb-6 normal-case">Distribution across the scale</p>
              <RatingHistogram distribution={stats.rating_distribution ?? {}} />
            </section>
          </div>

          {Object.keys(stats.decades ?? {}).length > 0 && (
            <section className="panel p-6">
              <h2 className="slate-label mb-1">Eras you watch</h2>
              <p className="tech mb-6 normal-case">Release decade of everything you have rated</p>
              <BarList
                items={Object.entries(stats.decades).map(([name, count]) => ({
                  name,
                  movie_count: count,
                }))}
                total={stats.ratings_count}
              />
            </section>
          )}

          <SpecSheet
            title="Profile summary"
            rows={[
              { label: 'Ratings on file', value: stats.ratings_count },
              { label: 'Mean score', value: stats.average_rating.toFixed(2), accent: true },
              { label: 'Watchlist', value: stats.watchlist_count },
              { label: 'Distinct genres', value: stats.top_genres?.length ?? 0 },
            ]}
          />

          <div className="flex flex-wrap gap-3">
            <Link to="/app/recommendations" className="btn-primary">
              See what this predicts
            </Link>
            <Link to="/app/ratings" className="btn-secondary">
              Manage ratings
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
