import { Link } from 'react-router-dom';

const COMPONENT_LABELS = {
  ials: 'Taste match',
  item_knn: 'Similar films',
  content: 'Themes & crew',
  quality: 'Standing',
};

/**
 * Why a film was recommended, set as a continuity note.
 *
 * The bars are each model's standardised contribution to the blended score, and
 * `because_of` lists the films from the user's own history that drove it. Both
 * come from the engine, so the panel cannot claim a reason the model did not use.
 *
 * Contributions are z-scores and therefore signed. Only positive ones are shown:
 * a negative bar means the film scored below average on that signal, which has no
 * useful reading as an explanation.
 */
export default function ExplanationCard({ explanation, compact = false }) {
  if (!explanation) return null;

  const contributions = Object.entries(explanation.components ?? {})
    .filter(([, value]) => value > 0.05)
    .sort((a, b) => b[1] - a[1]);

  const total = contributions.reduce((sum, [, value]) => sum + value, 0);

  if (compact) {
    return (
      <p className="flex items-center gap-2 border-l border-tungsten-500/50 pl-2.5 font-mono text-2xs text-print-400">
        <span className="truncate">{explanation.headline}</span>
      </p>
    );
  }

  return (
    <div className="border border-print-100/10 bg-film-900/60 p-4">
      <p className="slate-label mb-3">Continuity note</p>
      <p className="font-display text-sm uppercase tracking-slate text-print-100">
        {explanation.headline}
      </p>

      {explanation.because_of?.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {explanation.because_of.map((item) => (
            <Link key={item.movie_id} to={`/movie/${item.movie_id}`} className="chip">
              {item.title}
              <span className="tabular-nums text-print-500">{item.weight.toFixed(2)}</span>
            </Link>
          ))}
        </div>
      )}

      {explanation.shared_genres?.length > 0 && (
        <p className="tech mt-3 normal-case">
          Shared: {explanation.shared_genres.join(', ')}
        </p>
      )}

      {contributions.length > 0 && total > 0 && (
        <div className="mt-4 space-y-2">
          {contributions.map(([key, value]) => (
            <div key={key} className="flex items-center gap-3">
              <span className="w-24 shrink-0 font-mono text-[10px] uppercase tracking-wider text-print-500">
                {COMPONENT_LABELS[key] ?? key}
              </span>
              <span className="h-[3px] flex-1 bg-print-100/10">
                <span
                  className="block h-full bg-tungsten-500"
                  style={{ width: `${Math.round((value / total) * 100)}%` }}
                />
              </span>
              <span className="w-8 shrink-0 text-right font-mono text-[10px] tabular-nums text-print-500">
                {Math.round((value / total) * 100)}%
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
