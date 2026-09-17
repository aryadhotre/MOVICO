import Logo from './Logo';

/**
 * Route-transition fallback.
 *
 * Shows the brand mark rather than a bare spinner, because a lazily loaded chunk
 * usually resolves in well under a second and a flashing spinner reads as a
 * glitch. The pulse is slow enough not to draw the eye.
 */
export default function PageSpinner({ label = 'Loading' }) {
  return (
    <div className="flex min-h-[60svh] items-center justify-center" role="status" aria-live="polite">
      <div className="flex flex-col items-center gap-4">
        <div className="animate-pulse">
          <Logo size={38} showWordmark={false} />
        </div>
        <span className="sr-only">{label}</span>
      </div>
    </div>
  );
}
