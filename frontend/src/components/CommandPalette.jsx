import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { CornerDownLeft, Loader2, Search, Star } from 'lucide-react';
import { posterUrl } from '../lib/images';
import { useSearch } from '../lib/queries';

/**
 * Instant search overlay.
 *
 * The input is debounced by 180ms so typing "inception" costs one request rather
 * than nine, and React Query dedupes and caches whatever does go out. Results are
 * keyboard-navigable, which is the whole point of a palette — the mouse should be
 * optional.
 */
export default function CommandPalette({ open, onClose }) {
  const navigate = useNavigate();
  const inputRef = useRef(null);
  const [term, setTerm] = useState('');
  const [debounced, setDebounced] = useState('');
  const [cursor, setCursor] = useState(0);

  const { data, isFetching } = useSearch(debounced, { enabled: open });
  const results = data?.items ?? [];

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(term), 180);
    return () => clearTimeout(timer);
  }, [term]);

  useEffect(() => {
    setCursor(0);
  }, [debounced]);

  useEffect(() => {
    if (!open) {
      setTerm('');
      setDebounced('');
      return;
    }
    // Autofocus has to wait for the element to exist and the animation to start.
    const timer = setTimeout(() => inputRef.current?.focus(), 40);
    return () => clearTimeout(timer);
  }, [open]);

  // Lock background scroll while the overlay is up.
  useEffect(() => {
    if (!open) return undefined;
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previous;
    };
  }, [open]);

  const go = (movie) => {
    onClose();
    navigate(`/movie/${movie.id}`);
  };

  const onKeyDown = (event) => {
    if (event.key === 'Escape') {
      onClose();
    } else if (event.key === 'ArrowDown') {
      event.preventDefault();
      setCursor((index) => Math.min(index + 1, Math.max(results.length - 1, 0)));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setCursor((index) => Math.max(index - 1, 0));
    } else if (event.key === 'Enter' && results[cursor]) {
      event.preventDefault();
      go(results[cursor]);
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[70] flex items-start justify-center px-4 pt-[12vh]"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
        >
          <div
            className="absolute inset-0 bg-ink-950/75 backdrop-blur-sm"
            onClick={onClose}
            aria-hidden="true"
          />

          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label="Search films"
            className="glass-strong relative w-full max-w-xl overflow-hidden rounded-2xl shadow-lift"
            initial={{ opacity: 0, y: -12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.99 }}
            transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
            onKeyDown={onKeyDown}
          >
            <div className="flex items-center gap-3 border-b border-white/[0.07] px-4">
              <Search className="h-4 w-4 shrink-0 text-white/35" />
              <input
                ref={inputRef}
                value={term}
                onChange={(event) => setTerm(event.target.value)}
                placeholder="Search films, directors, actors…"
                aria-label="Search films"
                className="w-full bg-transparent py-4 text-[15px] text-white placeholder:text-white/30 focus:outline-none"
              />
              {isFetching && <Loader2 className="h-4 w-4 shrink-0 animate-spin text-white/35" />}
              <kbd className="hidden shrink-0 rounded border border-white/10 bg-white/[0.06] px-1.5 py-0.5 text-2xs text-white/40 sm:block">
                esc
              </kbd>
            </div>

            <div className="max-h-[52vh] overflow-y-auto p-2">
              {debounced.length < 2 ? (
                <p className="px-3 py-8 text-center text-sm text-white/35">
                  Type at least two characters to search.
                </p>
              ) : results.length === 0 && !isFetching ? (
                <p className="px-3 py-8 text-center text-sm text-white/35">
                  Nothing matched “{debounced}”.
                </p>
              ) : (
                results.map((movie, index) => (
                  <button
                    key={movie.id}
                    type="button"
                    onClick={() => go(movie)}
                    onMouseEnter={() => setCursor(index)}
                    className={`flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left transition-colors ${
                      index === cursor ? 'bg-white/[0.08]' : 'hover:bg-white/[0.05]'
                    }`}
                  >
                    {movie.poster_path ? (
                      <img
                        src={posterUrl(movie.poster_path, 92)}
                        alt=""
                        loading="lazy"
                        decoding="async"
                        className="h-14 w-[38px] shrink-0 rounded-md object-cover"
                      />
                    ) : (
                      <div className="h-14 w-[38px] shrink-0 rounded-md bg-ink-800" />
                    )}

                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium text-white">
                        {movie.title}
                      </span>
                      <span className="mt-0.5 flex items-center gap-2 text-2xs text-white/45">
                        {movie.year && <span className="tabular-nums">{movie.year}</span>}
                        {movie.genres?.length > 0 && (
                          <span className="truncate">{movie.genres.slice(0, 2).join(' · ')}</span>
                        )}
                      </span>
                    </span>

                    {movie.vote_average > 0 && (
                      <span className="flex shrink-0 items-center gap-1 text-2xs font-semibold text-amber-500">
                        <Star className="h-3 w-3" style={{ fill: 'currentColor' }} />
                        {movie.vote_average.toFixed(1)}
                      </span>
                    )}

                    {index === cursor && (
                      <CornerDownLeft className="h-3.5 w-3.5 shrink-0 text-white/30" />
                    )}
                  </button>
                ))
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
