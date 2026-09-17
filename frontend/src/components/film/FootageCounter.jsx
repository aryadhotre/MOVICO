import { motion, useScroll, useSpring, useTransform } from 'framer-motion';

/**
 * Scroll progress, read as a film footage counter.
 *
 * A projectionist tracks position through a reel in feet, not percent, and a
 * 35mm print runs 90 feet per minute at 24fps. Mapping scroll depth onto a
 * footage reading turns a generic progress bar into an instrument that belongs to
 * the medium — and it still communicates exactly what a progress bar would.
 *
 * The bar itself is spring-damped so it trails the scroll slightly instead of
 * tracking it rigidly, which is what stops it reading as a raw scrollbar.
 */
export default function FootageCounter({ total = 2400 }) {
  const { scrollYProgress } = useScroll();
  const smooth = useSpring(scrollYProgress, { stiffness: 120, damping: 28, restDelta: 0.001 });
  const width = useTransform(smooth, [0, 1], ['0%', '100%']);
  const feet = useTransform(smooth, (value) => `${Math.round(value * total)} ft`);

  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-x-0 top-0 z-[60] hidden md:block"
    >
      <div className="relative h-[2px] w-full bg-print-100/[0.07]">
        <motion.div style={{ width }} className="h-full bg-tungsten-500" />
      </div>

      <motion.span
        style={{ left: width }}
        className="absolute top-3 -translate-x-1/2 whitespace-nowrap font-mono text-[10px] tabular-nums text-tungsten-500/70"
      >
        <motion.span>{feet}</motion.span>
      </motion.span>
    </div>
  );
}
