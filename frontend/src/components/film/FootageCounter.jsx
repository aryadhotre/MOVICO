import { motion, useScroll, useSpring, useTransform } from 'framer-motion';

/**
 * Scroll progress, read as a film footage counter.
 *
 * A projectionist tracks position through a reel in feet, not percent — a 35mm
 * print runs 90 feet per minute at 24fps — so mapping scroll depth onto a footage
 * reading turns a generic progress bar into an instrument belonging to the medium
 * while still communicating exactly what a progress bar would.
 *
 * The readout is parked in the bottom-left rather than riding the bar. Following
 * the bar's leading edge meant it started clipped against the viewport edge at 0%
 * and then travelled straight through the header logo — and at z-60 it sat *over*
 * the header rather than under it. A fixed corner has neither problem.
 *
 * The bar is spring-damped so it trails the scroll slightly instead of tracking it
 * rigidly, which is what stops it reading as a raw scrollbar.
 */
export default function FootageCounter({ total = 2400 }) {
  const { scrollYProgress } = useScroll();
  const smooth = useSpring(scrollYProgress, { stiffness: 120, damping: 28, restDelta: 0.001 });
  const width = useTransform(smooth, [0, 1], ['0%', '100%']);
  const feet = useTransform(smooth, (value) => String(Math.round(value * total)).padStart(4, '0'));
  // Fades in once the reel is actually running, so it does not sit at 0000 on load.
  const opacity = useTransform(smooth, [0, 0.02, 0.9, 1], [0, 1, 1, 0.6]);

  return (
    <>
      {/* Beneath the header (z-40) rather than over it. */}
      <div
        aria-hidden="true"
        className="pointer-events-none fixed inset-x-0 top-0 z-[35] h-[2px] bg-print-100/[0.07]"
      >
        <motion.div style={{ width }} className="h-full bg-tungsten-500" />
      </div>

      <motion.div
        aria-hidden="true"
        style={{ opacity }}
        className="pointer-events-none fixed bottom-6 left-6 z-[35] hidden items-center gap-2 lg:flex"
      >
        <span className="h-[1px] w-6 bg-tungsten-500/50" />
        <motion.span className="font-mono text-[10px] tabular-nums tracking-wider text-tungsten-500/80">
          {feet}
        </motion.span>
        <span className="font-mono text-[10px] tracking-wider text-print-500">ft</span>
      </motion.div>
    </>
  );
}
