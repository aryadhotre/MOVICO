import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Bookmark, Clapperboard, Compass, LogOut, Search, Star, User as UserIcon } from 'lucide-react';
import Logo from './Logo';
import CommandPalette from './CommandPalette';
import ShortcutsOverlay, { useShortcuts } from './ShortcutsOverlay';
import { useAuth } from '../lib/auth';

const NAV = [
  { to: '/app', label: 'Now showing', icon: Clapperboard, end: true },
  { to: '/app/recommendations', label: 'Selected for you', icon: Star },
  { to: '/app/browse', label: 'Catalogue', icon: Compass },
  { to: '/app/watchlist', label: 'Watchlist', icon: Bookmark },
  { to: '/app/ratings', label: 'Your ratings', icon: Star },
  { to: '/app/profile', label: 'Taste profile', icon: UserIcon },
];

const MOBILE_NAV = [NAV[0], NAV[1], NAV[2], NAV[3], NAV[5]];

export default function Layout() {
  const { user, signOut } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' });
  }, [location.pathname]);

  useShortcuts(navigate, {
    onSearch: () => setPaletteOpen(true),
    onHelp: () => setShortcutsOpen((open) => !open),
  });

  return (
    <div className="min-h-screen">
      {/* -------------------------------------------------------------- rail */}
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-[236px] flex-col border-r border-print-100/[0.08] bg-film-950/85 backdrop-blur-xl lg:flex">
        <div className="px-6 py-6">
          <Link to="/app" aria-label="MOVICO home">
            <Logo size={25} />
          </Link>
        </div>

        <nav className="flex-1 px-3" aria-label="Main">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `relative flex items-center gap-3 px-3 py-3 font-display text-2xs uppercase tracking-slate transition-colors duration-200 ${
                  isActive
                    ? 'text-tungsten-400'
                    : 'text-print-400 hover:text-print-100'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  {/* Tungsten bar marking the active reel. */}
                  {isActive && (
                    <span className="absolute left-0 top-1/2 h-6 w-[2px] -translate-y-1/2 bg-tungsten-500" />
                  )}
                  <Icon className="h-4 w-4 shrink-0" strokeWidth={1.8} />
                  {label}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-print-100/[0.08] p-3">
          <button
            type="button"
            onClick={() => setPaletteOpen(true)}
            className="mb-3 flex w-full items-center gap-2.5 border border-print-100/12 px-3 py-2.5 text-left transition-colors hover:border-tungsten-500/60"
          >
            <Search className="h-3.5 w-3.5 text-print-400" strokeWidth={2} />
            <span className="flex-1 font-mono text-2xs uppercase tracking-wider text-print-400">
              Search
            </span>
            <kbd className="border border-print-100/12 px-1.5 py-0.5 font-mono text-[10px] text-print-500">
              ⌘K
            </kbd>
          </button>

          <button
            type="button"
            onClick={() => setShortcutsOpen(true)}
            className="mb-3 w-full text-left font-mono text-[10px] uppercase tracking-wider text-print-500 transition-colors hover:text-tungsten-400"
          >
            Press ? for shortcuts
          </button>

          <div className="flex items-center gap-3 px-1 py-2">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center border border-tungsten-500/50 font-mono text-2xs uppercase text-tungsten-400">
              {user?.username?.slice(0, 2)}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate font-display text-2xs uppercase tracking-slate text-print-100">
                {user?.username}
              </p>
              <p className="truncate font-mono text-[10px] text-print-500">{user?.email}</p>
            </div>
            <button
              type="button"
              onClick={signOut}
              aria-label="Sign out"
              className="btn-ghost h-8 w-8 p-0"
            >
              <LogOut className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </aside>

      {/* ------------------------------------------------------ mobile header */}
      <header className="sticky top-0 z-40 flex items-center justify-between border-b border-print-100/[0.08] bg-film-950/90 px-5 py-3 backdrop-blur-xl lg:hidden">
        <Link to="/app" aria-label="MOVICO home">
          <Logo size={23} />
        </Link>
        <div className="flex items-center gap-1.5">
          <button type="button" onClick={() => setPaletteOpen(true)} aria-label="Search" className="btn-icon">
            <Search className="h-4 w-4" />
          </button>
          <button type="button" onClick={signOut} aria-label="Sign out" className="btn-icon">
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </header>

      <main className="pb-24 lg:pb-16 lg:pl-[236px]">
        <Outlet />
      </main>

      {/* ------------------------------------------------------ mobile tabbar */}
      <nav
        className="fixed inset-x-0 bottom-0 z-40 border-t border-print-100/[0.08] bg-film-950/95 backdrop-blur-xl lg:hidden"
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
                `flex flex-1 flex-col items-center gap-1 py-2.5 font-mono text-[10px] uppercase tracking-wider transition-colors ${
                  isActive ? 'text-tungsten-400' : 'text-print-500'
                }`
              }
            >
              <Icon className="h-[18px] w-[18px]" strokeWidth={1.9} />
              <span className="truncate px-1">{label.split(' ')[0]}</span>
            </NavLink>
          ))}
        </div>
      </nav>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
      <ShortcutsOverlay open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />
    </div>
  );
}
