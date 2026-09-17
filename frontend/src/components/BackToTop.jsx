import { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { ArrowUp } from 'lucide-react';

/**
 * Return to the top of a long page.
 *
 * Browse and the catalogue rows run to thousands of items with infinite scroll,
 * so the browser's own "scroll to top" is a long way from where the user ends up.
 * Appears only once there is a meaningful distance to travel back.
 *
 * Sits above the mobile tab bar rather than behind it.
 */
export default function BackToTop({ threshold = 1400 }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const onScroll = () => setVisible(window.scrollY > threshold);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, [threshold]);

  return (
    <AnimatePresence>
      {visible && (
        <motion.button
          type="button"
          onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
          aria-label="Back to top"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 8 }}
          transition={{ duration: 0.2 }}
          className="fixed bottom-24 right-5 z-50 flex h-11 w-11 items-center justify-center
                     border border-print-100/15 bg-film-900/90 text-print-200 backdrop-blur
                     transition-colors hover:border-tungsten-500 hover:text-tungsten-400
                     lg:bottom-8 lg:right-8"
        >
          <ArrowUp className="h-4 w-4" />
        </motion.button>
      )}
    </AnimatePresence>
  );
}
