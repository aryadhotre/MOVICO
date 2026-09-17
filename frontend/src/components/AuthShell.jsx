import { Link } from 'react-router-dom';
import Logo from './Logo';

/**
 * Split layout for sign-in and sign-up.
 *
 * The right panel is decorative and hidden below `lg`, so a phone gets the form at
 * full width instead of a squeezed two-column compromise.
 */
export default function AuthShell({ title, subtitle, children, footer, aside }) {
  return (
    <div className="flex min-h-screen">
      <div className="flex w-full flex-col justify-center px-6 py-12 lg:w-[52%] lg:px-16">
        <div className="mx-auto w-full max-w-sm">
          <Link to="/" className="mb-12 inline-flex" aria-label="MOVICO home">
            <Logo size={30} />
          </Link>

          <h1 className="text-3xl font-semibold tracking-tightest text-white">{title}</h1>
          {subtitle && <p className="mt-2.5 text-sm leading-relaxed text-white/50">{subtitle}</p>}

          <div className="mt-9">{children}</div>

          {footer && <div className="mt-8 text-sm text-white/45">{footer}</div>}
        </div>
      </div>

      <div className="relative hidden flex-1 overflow-hidden border-l border-white/[0.06] lg:block">
        <div className="absolute inset-0 bg-[radial-gradient(45rem_30rem_at_60%_30%,rgba(124,92,255,0.22),transparent_65%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(35rem_25rem_at_30%_80%,rgba(255,77,141,0.16),transparent_60%)]" />
        <div className="noise absolute inset-0" />
        <div className="relative flex h-full items-center justify-center p-16">{aside}</div>
      </div>
    </div>
  );
}
