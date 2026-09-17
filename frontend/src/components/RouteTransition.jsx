import { motion, useReducedMotion } from 'framer-motion';
import { useLocation } from 'react-router-dom';

/**
 * A short settle on route change.
 *
 * Keyed on the pathname with no exit animation, deliberately. `AnimatePresence`
 * around lazily loaded routes has to hold the outgoing tree mounted while the
 * incoming chunk is still resolving, which produces a flash of two pages or a
 * stall on the first visit to each route. Animating only the entry gives the
 * transition its meaning — the new page settles into place — at no risk.
 *
 * 220ms: long enough to read as deliberate, short enough that it never stands
 * between a click and the content.
 */
export default function RouteTransition({ children }) {
  const location = useLocation();
  const reduce = useReducedMotion();

  if (reduce) return children;

  return (
    <motion.div
      key={location.pathname}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}
