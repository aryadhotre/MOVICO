import { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Keyboard, X } from 'lucide-react';

const GROUPS = [
  {
    title: 'Navigation',
    items: [
      [['g', 'h'], 'Now showing'],
      [['g', 'f'], 'Selected for you'],
      [['g', 'c'], 'Catalogue'],
      [['g', 'w'], 'Watchlist'],
      [['g', 'p'], 'Taste profile'],
    ],
  },
  {
    title: 'Actions',
    items: [
      [['⌘', 'K'], 'Search'],
      [['?'], 'This panel'],
      [['Esc'], 'Close'],
    ],
  },
];

function Key({ children }) {
  return (
    <kbd className="inline-flex h-6 min-w-6 items-center justify-center border border-print-100/20 bg-film-800 px-1.5 font-mono text-[10px] text-print-200">
      {children}
    </kbd>
  );
}

/**
 * Keyboard shortcut reference, opened with `?`.
 *
 * Discoverability is the whole point: shortcuts nobody knows about are shortcuts
 * nobody uses, and every serious tool-style interface publishes them somewhere.
 * The `g`-then-key chords follow the convention Gmail and GitHub established, so
 * the muscle memory transfers.
 */
export default function ShortcutsOverlay({ open, onClose }) {
  useEffect(() => {
    if (!open) return undefined;
    const handler = (event) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[85] flex items-center justify-center p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
        >
          <div className="absolute inset-0 bg-film-950/85 backdrop-blur-sm" onClick={onClose} />

          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label="Keyboard shortcuts"
            className="relative w-full max-w-lg border border-print-100/15 bg-film-900 shadow-lift"
            initial={{ opacity: 0, y: -10, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, scale: 0.99 }}
            transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="flex items-center justify-between border-b border-print-100/10 px-5 py-3">
              <span className="slate-label flex items-center gap-2">
                <Keyboard className="h-3.5 w-3.5" />
                Shortcuts
              </span>
              <button type="button" onClick={onClose} aria-label="Close" className="btn-ghost h-7 w-7 p-0">
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="grid gap-8 p-6 sm:grid-cols-2">
              {GROUPS.map((group) => (
                <div key={group.title}>
                  <p className="tech mb-4">{group.title}</p>
                  <ul className="space-y-3">
                    {group.items.map(([keys, label]) => (
                      <li key={label} className="flex items-center justify-between gap-4">
                        <span className="text-sm text-print-300">{label}</span>
                        <span className="flex shrink-0 items-center gap-1">
                          {keys.map((key, index) => (
                            <span key={index} className="flex items-center gap-1">
                              {index > 0 && <span className="text-[10px] text-print-500">then</span>}
                              <Key>{key}</Key>
                            </span>
                          ))}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/**
 * Wires the global shortcut handling.
 *
 * Chords time out after a second so a stray `g` does not sit armed indefinitely,
 * and every handler bails when focus is inside a text field — otherwise typing
 * "grid" into the search box would navigate away mid-word.
 */
export function useShortcuts(navigate, { onSearch, onHelp }) {
  const [pending, setPending] = useState(null);

  useEffect(() => {
    const isTyping = () => {
      const node = document.activeElement;
      if (!node) return false;
      return (
        node.tagName === 'INPUT' ||
        node.tagName === 'TEXTAREA' ||
        node.tagName === 'SELECT' ||
        node.isContentEditable
      );
    };

    const routes = {
      h: '/app',
      f: '/app/recommendations',
      c: '/app/browse',
      w: '/app/watchlist',
      p: '/app/profile',
      r: '/app/ratings',
    };

    const handler = (event) => {
      if (isTyping()) return;

      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        onSearch();
        return;
      }
      if (event.metaKey || event.ctrlKey || event.altKey) return;

      if (event.key === '?') {
        event.preventDefault();
        onHelp();
        return;
      }

      const key = event.key.toLowerCase();

      if (pending === 'g') {
        setPending(null);
        if (routes[key]) {
          event.preventDefault();
          navigate(routes[key]);
        }
        return;
      }

      if (key === 'g') {
        setPending('g');
        setTimeout(() => setPending(null), 1000);
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [pending, navigate, onSearch, onHelp]);
}
