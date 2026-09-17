import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { AlertTriangle, Bookmark, Check, Star, X } from 'lucide-react';

const ToastContext = createContext(null);

const ICONS = { success: Check, rating: Star, watchlist: Bookmark, error: AlertTriangle };

/**
 * Transient confirmation for actions that otherwise happen silently.
 *
 * Rating a film and saving one both mutate optimistically, so the UI updates
 * instantly — which is fast but leaves no trace that anything was recorded. A
 * short acknowledgement closes that loop.
 *
 * `aria-live="polite"` rather than "assertive": these confirm a deliberate action
 * the user just took, so interrupting a screen reader mid-sentence would be rude.
 */
export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const counter = useRef(0);

  const dismiss = useCallback((id) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const push = useCallback(
    ({ message, detail = null, kind = 'success', duration = 2600 }) => {
      counter.current += 1;
      const id = counter.current;
      setToasts((current) => {
        // Cap the stack: beyond three, older ones are noise.
        const next = [...current, { id, message, detail, kind }];
        return next.slice(-3);
      });
      if (duration) setTimeout(() => dismiss(id), duration);
      return id;
    },
    [dismiss],
  );

  const value = useMemo(() => ({ push, dismiss }), [push, dismiss]);

  return (
    <ToastContext.Provider value={value}>
      {children}

      <div
        className="pointer-events-none fixed bottom-24 left-1/2 z-[90] flex w-[min(92vw,26rem)] -translate-x-1/2 flex-col gap-2 lg:bottom-8 lg:left-auto lg:right-8 lg:translate-x-0"
        role="status"
        aria-live="polite"
      >
        <AnimatePresence initial={false}>
          {toasts.map((toast) => {
            const Icon = ICONS[toast.kind] ?? Check;
            const isError = toast.kind === 'error';
            return (
              <motion.div
                key={toast.id}
                layout
                initial={{ opacity: 0, y: 16, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 8, scale: 0.98 }}
                transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
                className={`pointer-events-auto flex items-center gap-3 border px-4 py-3 backdrop-blur-xl ${
                  isError
                    ? 'border-reel-500/50 bg-reel-600/15'
                    : 'border-print-100/15 bg-film-850/95'
                }`}
              >
                <Icon
                  className={`h-4 w-4 shrink-0 ${isError ? 'text-reel-400' : 'text-tungsten-500'}`}
                  strokeWidth={2}
                />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-display text-2xs uppercase tracking-slate text-print-100">
                    {toast.message}
                  </p>
                  {toast.detail && (
                    <p className="mt-0.5 truncate font-mono text-[10px] text-print-400">
                      {toast.detail}
                    </p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => dismiss(toast.id)}
                  aria-label="Dismiss"
                  className="shrink-0 text-print-500 transition-colors hover:text-print-100"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  // Returning a no-op keeps components usable outside the provider (tests,
  // isolated rendering) instead of throwing.
  return context ?? { push: () => {}, dismiss: () => {} };
}
