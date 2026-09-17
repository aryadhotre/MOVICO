import { Link } from 'react-router-dom';

/**
 * The placeholder shown when a collection is legitimately empty.
 *
 * Always offers the next action. An empty watchlist that only says "nothing here"
 * is a dead end; one with a link to browse is a prompt.
 */
export default function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="flex flex-col items-center justify-center border border-dashed border-print-100/12 px-6 py-24 text-center">
      {Icon && (
        <span className="mb-6 flex h-12 w-12 items-center justify-center border border-print-100/12 text-print-500">
          <Icon className="h-5 w-5" strokeWidth={1.5} />
        </span>
      )}
      <h3 className="title-card text-lg text-print-50">{title}</h3>
      {description && (
        <p className="mt-3 max-w-sm text-pretty text-sm leading-relaxed text-print-400">
          {description}
        </p>
      )}
      {action && (
        <Link to={action.to} className="btn-primary mt-8">
          {action.label}
        </Link>
      )}
    </div>
  );
}
