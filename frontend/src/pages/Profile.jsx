import { Link } from 'react-router-dom';
import { Bookmark, Star, TrendingUp, User as UserIcon } from 'lucide-react';
import EmptyState from '../components/EmptyState';
import { useTasteStats } from '../lib/queries';
import { useAuth } from '../lib/auth';

/**
 * Horizontal bars for genre affinity.
 *
 * Drawn with divs rather than a charting library: the shapes are trivial, and
 * pulling in a chart runtime for four bar rows would cost more bundle than the
 * whole page. Values are normalised against the largest so the longest bar always
 * fills the track.
 */
function BarList({ items, total }) {
  const max = Math.max(...items.map((item) => item.movie_count), 1);

  return (
    <ul className="space-y-3">
      {items.map(({ name, movie_count: count }) => (
        <li key={name}>
          <div className="mb-1.5 flex items-baseline justify-between gap-3 text-2xs">
            <span className="truncate font-medium text-white/75">{name}</span>
            <span className="shrink-0 tabular-nums text-white/35">
              {count}
              {total ? ` · ${Math.round((count / total) * 100)}%` : ''}
            </span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
            <div
              className="h-full rounded-full bg-brand-gradient transition-[width] duration-700 ease-smooth"
              style={{ width: `${(count / max) * 100}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}

/** Vertical histogram of the user's rating distribution. */
function RatingHistogram({ distribution }) {
  const buckets = ['0.5', '1', '1.5', '2', '2.5', '3', '3.5', '4', '4.5', '5'];
  const max = Math.max(...buckets.map((key) => distribution[key] ?? 0), 1);

  return (
    <div className="flex h-36 items-end gap-1.5">
      {buckets.map((key) => {
        const count = distribution[key] ?? 0;
        return (
          <div key={key} className="flex flex-1 flex-col items-center gap-1.5">
            <span className="text-2xs tabular-nums text-white/30">{count || ''}</span>
            <div
              className="w-full rounded-t bg-brand-gradient transition-[height] duration-700 ease-smooth"
              // A floor of 2px keeps empty buckets visible as a baseline.
              style={{ height: `${Math.max((count / max) * 100, count ? 6 : 2)}%` }}
              title={`${count} rated ${key}`}
            />
            <span className="text-2xs tabular-nums text-white/35">{key}</span>
          </div>
        );
      })}
    </div>
  );
}

function StatTile({ icon: Icon, label, value, hint }) {
  return (
    <div className="card-hairline p-5">
      <Icon className="h-4 w-4 text-violet-400" strokeWidth={2} />
      <p className="mt-3 text-2xl font-semibold tabular-nums tracking-tightest text-white">
        {value}
      </p>
      <p className="mt-0.5 text-2xs text-white/45">{label}</p>
      {hint && <p className="mt-1 text-2xs text-white/25">{hint}</p>}
    </div>
  );
}

export default function Profile() {
  const { user } = useAuth();
  const { data: stats, isLoading } = useTasteStats();

  const initials = user?.username?.slice(0, 2)?.toUpperCase() ?? '··';

  return (
    <div className="mx-auto max-w-5xl px-5 py-8 sm:px-6">
      <header className="mb-10 flex flex-wrap items-center gap-5">
        <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-brand-gradient text-xl font-bold text-white shadow-glow">
          {initials}
        </div>
        <div className="min-w-0">
          <h1 className="truncate text-2xl font-semibold tracking-tightest text-white">
            {user?.username}
          </h1>
          <p className="truncate text-sm text-white/45">{user?.email}</p>
          {user?.created_at && (
            <p className="mt-0.5 text-2xs text-white/30">
              Joined {new Date(user.created_at).toLocaleDateString()}
            </p>
          )}
        </div>
      </header>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-3">
          {Array.from({ length: 3 }, (_, index) => (
            <div key={index} className="skeleton h-32" />
          ))}
        </div>
      ) : !stats || stats.ratings_count === 0 ? (
        <EmptyState
          icon={UserIcon}
          title="No taste profile yet"
          description="Rate a handful of films and this page will fill in with your genre balance, rating spread and the decades you lean toward."
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
            <section className="card-hairline p-6">
              <h2 className="text-base font-semibold text-white">Genres you gravitate to</h2>
              <p className="mb-5 mt-1 text-2xs text-white/35">
                Counted from films you rated 3.5 or higher
              </p>
              {stats.top_genres?.length > 0 ? (
                <BarList items={stats.top_genres} total={stats.ratings_count} />
              ) : (
                <p className="text-sm text-white/35">
                  Rate a few films positively to see this.
                </p>
              )}
            </section>

            <section className="card-hairline p-6">
              <h2 className="text-base font-semibold text-white">How you rate</h2>
              <p className="mb-5 mt-1 text-2xs text-white/35">Distribution across the scale</p>
              <RatingHistogram distribution={stats.rating_distribution ?? {}} />
            </section>
          </div>

          {Object.keys(stats.decades ?? {}).length > 0 && (
            <section className="card-hairline p-6">
              <h2 className="text-base font-semibold text-white">Eras you watch</h2>
              <p className="mb-5 mt-1 text-2xs text-white/35">
                Release decade of everything you&apos;ve rated
              </p>
              <BarList
                items={Object.entries(stats.decades).map(([name, count]) => ({
                  name,
                  movie_count: count,
                }))}
                total={stats.ratings_count}
              />
            </section>
          )}

          <div className="flex flex-wrap gap-3">
            <Link to="/app/recommendations" className="btn-primary px-5 py-2.5">
              See what this predicts
            </Link>
            <Link to="/app/ratings" className="btn-secondary px-5 py-2.5">
              Manage ratings
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
