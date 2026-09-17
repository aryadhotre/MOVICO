import { useState } from 'react';
import { Link, Outlet } from 'react-router-dom';
import { ArrowRight, Search } from 'lucide-react';
import Logo from './Logo';
import CommandPalette from './CommandPalette';
import { useAuth } from '../lib/auth';

/**
 * Chrome for pages a signed-out visitor can reach (catalogue browse, film detail).
 *
 * Browsing without an account matters: it lets someone see the catalogue is real
 * before committing, and it gives film pages a URL that can be shared with anyone.
 */
export default function PublicShell() {
  const { isAuthenticated } = useAuth();
  const [paletteOpen, setPaletteOpen] = useState(false);

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-50 border-b border-white/[0.06] bg-ink-950/75 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[1500px] items-center justify-between gap-4 px-5 py-3">
          <Link to={isAuthenticated ? '/app' : '/'} aria-label="MOVICO home">
            <Logo size={26} />
          </Link>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setPaletteOpen(true)}
              className="flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.04] px-3.5 py-2 text-sm text-white/45 transition-colors hover:border-white/15 hover:text-white/75"
            >
              <Search className="h-4 w-4" strokeWidth={2} />
              <span className="hidden sm:inline">Search</span>
            </button>

            {isAuthenticated ? (
              <Link to="/app" className="btn-primary px-4 py-2">
                Open app
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            ) : (
              <>
                <Link to="/login" className="btn-ghost hidden text-sm sm:inline-flex">
                  Sign in
                </Link>
                <Link to="/signup" className="btn-primary px-4 py-2">
                  Get started
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="pb-20">
        <Outlet />
      </main>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  );
}
