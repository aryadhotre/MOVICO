import { Link } from 'react-router-dom';
import Logo from './Logo';
import Perforations from './film/Perforations';

/**
 * Split layout for sign-in and sign-up.
 *
 * The right panel is a projection plate — a still frame with grain and a tungsten
 * wash — separated from the form by a strip of sprocket holes. Hidden below `lg`
 * so a phone gets the form at full width rather than a squeezed two-column
 * compromise.
 */
export default function AuthShell({ title, subtitle, children, footer, aside }) {
  return (
    <div className="flex min-h-screen">
      <div className="flex w-full flex-col justify-center px-6 py-12 lg:w-[50%] lg:px-20">
        <div className="mx-auto w-full max-w-sm">
          <Link to="/" className="mb-14 inline-flex" aria-label="MOVICO home">
            <Logo size={26} />
          </Link>

          <p className="slate-label mb-3">{subtitle ? 'Access' : 'Welcome'}</p>
          <h1 className="title-card text-3xl text-print-50">{title}</h1>
          {subtitle && (
            <p className="mt-4 text-sm leading-relaxed text-print-400">{subtitle}</p>
          )}

          <div className="mt-10">{children}</div>

          {footer && <div className="mt-8 text-sm text-print-400">{footer}</div>}
        </div>
      </div>

      <div className="relative hidden flex-1 lg:flex">
        <Perforations orientation="vertical" />

        <div className="relative flex-1 overflow-hidden bg-film-900">
          <div className="absolute inset-0 bg-[radial-gradient(40rem_28rem_at_55%_35%,rgba(237,163,44,0.18),transparent_65%)]" />
          <div className="absolute inset-0 bg-[radial-gradient(32rem_24rem_at_25%_85%,rgba(51,184,168,0.10),transparent_60%)]" />
          <div className="grain absolute inset-0" />
          <div className="absolute inset-0 vignette" />
          <div className="relative flex h-full items-center justify-center p-20">{aside}</div>
        </div>
      </div>
    </div>
  );
}
