/**
 * A technical specification block, set the way a camera report or a print's
 * technical data sheet would be: monospaced, left-aligned, leader-dotted, with
 * the value doing the talking.
 *
 * Used for film metadata on the detail page and for the model's evaluation
 * figures on the landing page — both are, literally, technical specifications.
 */
export function SpecRow({ label, value, accent = false, note = null }) {
  if (value === null || value === undefined || value === '') return null;

  return (
    <div className="flex items-baseline gap-3 py-2">
      <span className="tech shrink-0 text-print-500">{label}</span>
      <span className="min-w-0 flex-1 translate-y-[-3px] border-b border-dotted border-print-100/15" />
      <span
        className={`shrink-0 text-right font-mono text-xs tabular-nums ${
          accent ? 'text-tungsten-400' : 'text-print-100'
        }`}
      >
        {value}
        {note && <span className="ml-2 text-print-500">{note}</span>}
      </span>
    </div>
  );
}

export default function SpecSheet({ title, rows = [], children, className = '' }) {
  return (
    <div className={`panel p-5 ${className}`}>
      {title && (
        <h3 className="slate-label mb-3 border-b border-print-100/10 pb-3">{title}</h3>
      )}
      <div className="divide-y divide-print-100/[0.06]">
        {rows.map((row) => (
          <SpecRow key={row.label} {...row} />
        ))}
      </div>
      {children}
    </div>
  );
}
