import AcademyLeader from './film/AcademyLeader';

/** Route-transition fallback: a countdown leader, as a print would open with. */
export default function PageSpinner({ label = 'Loading' }) {
  return (
    <div className="flex min-h-[60svh] flex-col items-center justify-center gap-6">
      <AcademyLeader size={120} label={label} />
      <p className="tech animate-flicker">Threading reel…</p>
    </div>
  );
}
