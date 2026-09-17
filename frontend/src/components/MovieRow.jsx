import { useCallback, useEffect, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import MovieCard from './MovieCard';

const CARD_WIDTH =
  'w-[42vw] shrink-0 xs:w-[34vw] sm:w-[27vw] md:w-[20vw] lg:w-[15vw] xl:w-[12.2vw]';

function CardSkeleton() {
  return (
    <div className={CARD_WIDTH}>
      <div className="skeleton aspect-[2/3] w-full" />
      <div className="skeleton mt-2.5 h-3 w-4/5" />
      <div className="skeleton mt-1.5 h-2 w-1/2" />
    </div>
  );
}

/**
 * A horizontal carousel, framed as a reel.
 *
 * Native overflow scrolling with scroll-snap rather than a transform carousel, so
 * touch, trackpad, keyboard and screen-reader navigation all behave the way the
 * platform already does. The arrows are a pointer affordance layered on top, and
 * they disable at the ends so the control never lies about what it can do.
 *
 * The progress rule under the header tracks scroll position: on a row of forty
 * titles the scrollbar is hidden, so without it there is no indication of how
 * much remains.
 */
export default function MovieRow({
  title,
  subtitle,
  items = [],
  loading = false,
  numbered = false,
  spined = false,
  showMatch = false,
  action = null,
  priorityCount = 0,
}) {
  const scroller = useRef(null);
  const [atStart, setAtStart] = useState(true);
  const [atEnd, setAtEnd] = useState(false);
  const [progress, setProgress] = useState(0);
  const [scrollable, setScrollable] = useState(false);

  const syncEdges = useCallback(() => {
    const node = scroller.current;
    if (!node) return;
    const travel = node.scrollWidth - node.clientWidth;
    setAtStart(node.scrollLeft <= 4);
    setAtEnd(node.scrollLeft >= travel - 4);
    setScrollable(travel > 8);
    setProgress(travel > 0 ? node.scrollLeft / travel : 0);
  }, []);

  useEffect(() => {
    syncEdges();
    const node = scroller.current;
    if (!node) return undefined;
    // Catches the case where the row only becomes scrollable once posters load.
    const observer = new ResizeObserver(syncEdges);
    observer.observe(node);
    return () => observer.disconnect();
  }, [syncEdges, items.length]);

  const scrollBy = (direction) => {
    const node = scroller.current;
    if (!node) return;
    node.scrollBy({ left: direction * node.clientWidth * 0.82, behavior: 'smooth' });
  };

  if (!loading && items.length === 0) return null;

  return (
    <section className="group/row relative">
      <header className="mb-4 flex items-end justify-between gap-4">
        <div className="min-w-0">
          <h2 className="truncate font-display text-xl font-medium uppercase tracking-slate text-print-50 sm:text-2xl">
            {title}
          </h2>
          {subtitle && <p className="tech mt-1 truncate normal-case">{subtitle}</p>}
        </div>

        <div className="flex shrink-0 items-center gap-3">
          {action}

          {scrollable && (
            <div className="hidden h-[2px] w-16 bg-print-100/12 lg:block" aria-hidden="true">
              <div
                className="h-full bg-tungsten-500 transition-[width] duration-150 ease-out"
                style={{ width: `${Math.max(8, progress * 100)}%` }}
              />
            </div>
          )}

          <div className="hidden items-center gap-1.5 sm:flex">
            <button
              type="button"
              onClick={() => scrollBy(-1)}
              disabled={atStart}
              aria-label={`Scroll ${title} left`}
              className="btn-icon disabled:opacity-20"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={() => scrollBy(1)}
              disabled={atEnd}
              aria-label={`Scroll ${title} right`}
              className="btn-icon disabled:opacity-20"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </header>

      <div ref={scroller} onScroll={syncEdges} className="scroll-row">
        {loading
          ? Array.from({ length: 8 }, (_, index) => <CardSkeleton key={index} />)
          : items.map((movie, index) => (
              <MovieCard
                key={movie.id}
                movie={movie}
                rank={numbered ? index + 1 : null}
                spine={spined ? index + 1 : null}
                matchScore={showMatch ? movie.matchScore ?? null : null}
                priority={index < priorityCount}
                className={CARD_WIDTH}
              />
            ))}
      </div>
    </section>
  );
}
