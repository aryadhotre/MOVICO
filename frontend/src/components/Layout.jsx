import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';
import {
  Bookmark,
  Compass,
  Home,
  LogOut,
  Search,
  Sparkles,
  Star,
  User as UserIcon,
} from 'lucide-react';
import Logo from './Logo';
import CommandPalette from './CommandPalette';
import { useAuth } from '../lib/auth';

const NAV = [
  { to: '/app', label: 'Home', icon: Home, end: true },
  { to: '/app/recommendations', label: 'For you', icon: Sparkles },
  { to: '/app/browse', label: 'Browse', icon: Compass },
  { to: '/app/watchlist', label: 'Watchlist', icon: Bookmark },
  { to: '/app/ratings', label: 'Your ratings', icon: Star },
  { to: '/app/profile', label: 'Taste profile', icon: UserIcon },
];

/** Bottom tab bar items for small screens; the full nav does not fit. */
const MOBILE_NAV = NAV.slice(0, 5);

export default function Layout() {
  const { user, signOut } = useAuth();
  const location = useLocation();
  const [paletteOpen, setPaletteOpen] = useState(false);

  // Route changes should land at the top of the new page.
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' });
  }, [location.pathname]);

  useEffect(() => {
    const handler = (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setPaletteOpen(true);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  return (
    <div className="min-h-screen">
      {/* ------------------------------------------------------------ sidebar */}
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-[232px] flex-col border-r border-white/[0.06] bg-ink-950/70 backdrop-blur-xl lg:flex">
        <div className="px-5 py-5">
          <Link to="/app" className="inline-flex" aria-label="MOVICO home">
            <Logo size={28} />
          </Link>
        </div>

        <nav className="flex-1 space-y-0.5 px-3" aria-label="Main">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200 ease-smooth ${
                  isActive
                    ? 'bg-white/[0.07] text-white'
                    : 'text-white/55 hover:bg-white/[0.04] hover:text-white/90'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-brand-gradient" />
                  )}
                  <Icon className="h-[18px] w-[18px] shrink-0" strokeWidth={1.9} />
                  {label}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-white/[0.06] p-3">
          <button
            type="button"
            onClick={() => setPaletteOpen(true)}
            className="mb-2 flex w-full items-center gap-2.5 rounded-xl border border-white/[0.07] bg-white/[0.03] px-3 py-2.5 text-left text-sm text-white/45 transition-colors hover:border-white/15 hover:text-white/75"
          >
            <Search className="h-4 w-4" strokeWidth={1.9} />
            <span className="flex-1">Search</span>
            <kbd className="rounded border border-white/10 bg-white/[0.06] px-1.5 py-0.5 text-2xs font-sans text-white/50">
              ⌘K
            </kbd>
          </button>

          <div className="flex items-center gap-2.5 rounded-xl px-2 py-2">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-gradient text-xs font-bold uppercase text-white">
              {user?.username?.slice(0, 2) ?? '··'}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-white">{user?.username}</p>
              <p className="truncate text-2xs text-white/40">{user?.email}</p>
            </div>
            <button
              type="button"
              onClick={signOut}
              aria-label="Sign out"
              className="btn-ghost h-8 w-8 rounded-lg p-0"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* ------------------------------------------------------- mobile header */}
      <header className="sticky top-0 z-40 flex items-center justify-between gap-3 border-b border-white/[0.06] bg-ink-950/85 px-4 py-3 backdrop-blur-xl lg:hidden">
        <Link to="/app" aria-label="MOVICO home">
          <Logo size={26} />
        </Link>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => setPaletteOpen(true)}
            aria-label="Search"
            className="btn-icon"
          >
            <Search className="h-4 w-4" />
          </button>
          <button type="button" onClick={signOut} aria-label="Sign out" className="btn-icon">
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </header>

      {/* --------------------------------------------------------------- main */}
      <main className="pb-24 lg:pb-16 lg:pl-[232px]">
        <Outlet />
      </main>

      {/* ----------------------------------------------------- mobile tab bar */}
      <nav
        className="fixed inset-x-0 bottom-0 z-40 border-t border-white/[0.06] bg-ink-950/90 backdrop-blur-xl lg:hidden"
        aria-label="Main"
        style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
      >
        <div className="flex items-stretch">
          {MOBILE_NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex flex-1 flex-col items-center gap-1 py-2.5 text-2xs font-medium transition-colors ${
                  isActive ? 'text-violet-400' : 'text-white/45'
                }`
              }
            >
              <Icon className="h-[19px] w-[19px]" strokeWidth={2} />
              <span className="truncate px-1">{label}</span>
            </NavLink>
          ))}
        </div>
      </nav>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  );
}
