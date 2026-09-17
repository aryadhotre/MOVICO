import { Link } from 'react-router-dom';
import { Sparkles } from 'lucide-react';

/** Human labels for the engine's internal score components. */
const COMPONENT_LABELS = {
  ials: 'Taste match',
  item_knn: 'Similar films',
  content: 'Themes & crew',
  quality: 'Critical standing',
};

/**
 * Renders why a film was recommended.
 *
 * The bars show each model's standardised contribution to the blended score, and
 * `because_of` lists the films from the user's own profile that drove it. Both come
 * from the engine rather than being inferred here, so the panel cannot claim a
 * reason the model did not actually use.
 *
 * Contributions are z-scores, so they are signed — a negative value means the film
 * scored below average on that signal. Only positive ones are worth showing, since
 * a negative bar has no useful reading for a user.
 */
export default function ExplanationCard({ explanation, compact = false }) {
  if (!explanation) return null;

  const contributions = Object.entries(explanation.components ?? {})
    .filter(([, value]) => value > 0.05)
    .sort((a, b) => b[1] - a[1]);

  const total = contributions.reduce((sum, [, value]) => sum + value, 0);

  if (compact) {
    return (
      <p className="flex items-center gap-1.5 text-2xs text-white/45">
        <Sparkles className="h-3 w-3 shrink-0 text-violet-400" />
        <span className="truncate">{explanation.headline}</span>
      </p>
    );
  }

  return (
    <div className="rounded-xl border border-white/[0.07] bg-white/[0.025] p-4">
      <p className="flex items-center gap-2 text-sm font-medium text-white">
        <Sparkles className="h-3.5 w-3.5 shrink-0 text-violet-400" />
        {explanation.headline}
      </p>

      {explanation.because_of?.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {explanation.because_of.map((item) => (
            <Link
              key={item.movie_id}
              to={`/movie/${item.movie_id}`}
              className="chip transition-colors hover:border-white/25 hover:text-white"
            >
              {item.title}
              <span className="tabular-nums text-white/35">{item.weight.toFixed(2)}</span>
            </Link>
          ))}
        </div>
      )}

      {explanation.shared_genres?.length > 0 && (
        <p className="mt-3 text-2xs text-white/40">
          Shared genres: {explanation.shared_genres.join(', ')}
        </p>
      )}

      {contributions.length > 0 && total > 0 && (
        <div className="mt-4 space-y-2">
          {contributions.map(([key, value]) => (
            <div key={key} className="flex items-center gap-3">
              <span className="w-28 shrink-0 text-2xs text-white/45">
                {COMPONENT_LABELS[key] ?? key}
              </span>
              <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/[0.07]">
                <span
                  className="block h-full rounded-full bg-brand-gradient"
                  style={{ width: `${Math.round((value / total) * 100)}%` }}
                />
              </span>
              <span className="w-9 shrink-0 text-right text-2xs tabular-nums text-white/35">
                {Math.round((value / total) * 100)}%
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
