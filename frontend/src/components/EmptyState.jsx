import { Link } from 'react-router-dom';

/**
 * The placeholder shown when a collection is legitimately empty.
 *
 * Always offers the next action. An empty watchlist that only says "nothing here"
 * is a dead end; one with a link to browse is a prompt.
 */
export default function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-white/[0.09] px-6 py-20 text-center">
      {Icon && (
        <span className="mb-5 flex h-12 w-12 items-center justify-center rounded-2xl bg-white/[0.04] text-white/30">
          <Icon className="h-6 w-6" strokeWidth={1.6} />
        </span>
      )}
      <h3 className="text-lg font-semibold text-white">{title}</h3>
      {description && (
        <p className="mt-2 max-w-sm text-pretty text-sm leading-relaxed text-white/45">
          {description}
        </p>
      )}
      {action && (
        <Link to={action.to} className="btn-primary mt-7 px-5 py-2.5">
          {action.label}
        </Link>
      )}
    </div>
  );
}
