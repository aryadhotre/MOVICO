import { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';

import { API_WAKING_EVENT } from '../lib/api';

/**
 * Explains the first-request delay on a sleeping free-tier backend.
 *
 * The API sleeps after 15 minutes of inactivity and takes the better part of a
 * minute to wake. Without something saying so, the first visit of the day shows
 * empty shelves and a spinner that looks broken — the app's least forgiving
 * moment presented as a failure rather than as a known cost.
 *
 * Styled as a projectionist's cue rather than a browser warning: the footage
 * counter ticking up gives the wait a shape, which is the difference between
 * "slow" and "stuck". It appears only after a request has already run 2.5s, so
 * an awake backend never shows it.
 */
export default function WakingBanner() {
  const [waking, setWaking] = useState(false);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const handler = (event) => setWaking(Boolean(event.detail?.waking));
    window.addEventListener(API_WAKING_EVENT, handler);
    return () => window.removeEventListener(API_WAKING_EVENT, handler);
  }, []);

  useEffect(() => {
    if (!waking) {
      setElapsed(0);
      return undefined;
    }
    const started = Date.now();
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 250);
    return () => clearInterval(id);
  }, [waking]);

  return (
    <AnimatePresence>
      {waking && (
        <motion.div
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -12 }}
          transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
          className="fixed inset-x-0 top-0 z-[95] flex justify-center px-4 pt-3"
          role="status"
          aria-live="polite"
        >
          <div className="flex items-center gap-3 border border-tungsten-500/30 bg-film-850/95 px-4 py-2.5 backdrop-blur-xl">
            {/* The projector lamp warming up. */}
            <motion.span
              className="h-2 w-2 shrink-0 rounded-full bg-tungsten-500"
              animate={{ opacity: [0.25, 1, 0.25] }}
              transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }}
            />
            <p className="font-display text-2xs uppercase tracking-slate text-print-100">
              Warming the projector
            </p>
            <span className="font-mono text-[10px] tabular-nums text-print-400">
              {String(elapsed).padStart(2, '0')}s
            </span>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
