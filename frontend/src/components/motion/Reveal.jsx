import { useRef } from 'react';
import { motion, useInView, useReducedMotion } from 'framer-motion';

const EASE = [0.22, 1, 0.36, 1];

/** Fades a block up the first time it enters the viewport. */
export function Reveal({ children, delay = 0, y = 24, className = '', once = true }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once, margin: '-12% 0px' });
  const reduce = useReducedMotion();

  return (
    <motion.div
      ref={ref}
      className={className}
      initial={reduce ? false : { opacity: 0, y }}
      animate={inView || reduce ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.7, ease: EASE, delay }}
    >
      {children}
    </motion.div>
  );
}

/**
 * Reveals a heading word by word.
 *
 * Words rather than characters: per-character staggering on a display-size line
 * reads as a gimmick and, more practically, splitting into characters destroys
 * the text for a screen reader. The visible spans are hidden from assistive
 * technology and the whole string is exposed once, intact.
 */
export function RevealWords({ text, className = '', delay = 0, stagger = 0.055, as = 'h2' }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: '-14% 0px' });
  const reduce = useReducedMotion();
  const Component = motion[as] ?? motion.h2;

  if (reduce) {
    return <Component ref={ref} className={className}>{text}</Component>;
  }

  return (
    <Component ref={ref} className={className} aria-label={text}>
      {text.split(' ').map((word, index) => (
        <span
          key={`${word}-${index}`}
          aria-hidden="true"
          // The clipping wrapper is what makes the word rise *out of* the line
          // rather than simply fading in place.
          className="inline-block overflow-hidden align-bottom"
        >
          <motion.span
            className="inline-block"
            initial={{ y: '110%' }}
            animate={inView ? { y: 0 } : {}}
            transition={{ duration: 0.75, ease: EASE, delay: delay + index * stagger }}
          >
            {word}
            {/* A non-breaking space keeps the gap inside the animated span. */}
            {' '}
          </motion.span>
        </span>
      ))}
    </Component>
  );
}

/** Staggers a list of children in sequence. */
export function Stagger({ children, className = '', delay = 0, step = 0.07 }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: '-10% 0px' });
  const reduce = useReducedMotion();

  return (
    <div ref={ref} className={className}>
      {Array.isArray(children)
        ? children.map((child, index) => (
            <motion.div
              key={index}
              initial={reduce ? false : { opacity: 0, y: 18 }}
              animate={inView || reduce ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.6, ease: EASE, delay: delay + index * step }}
            >
              {child}
            </motion.div>
          ))
        : children}
    </div>
  );
}
