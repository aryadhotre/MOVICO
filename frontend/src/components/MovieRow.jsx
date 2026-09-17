import { useCallback, useEffect, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import MovieCard from './MovieCard';

function CardSkeleton() {
  return (
    <div className="w-[44vw] shrink-0 xs:w-[38vw] sm:w-[30vw] md:w-[22vw] lg:w-[15.5vw] xl:w-[12.5vw]">
      <div className="skeleton aspect-[2/3] w-full" />
      <div className="skeleton mt-2 h-3 w-4/5" />
    </div>
  );
}

/**
 * A horizontally scrollable carousel.
 *
 * Built on native overflow scrolling with scroll-snap rather than a transform
 * carousel, so touch and trackpad gestures, keyboard scrolling and screen-reader
 * navigation all behave the way the platform already does. The arrows are a
 * pointer affordance layered on top, and they hide themselves at the ends so the
 * control never lies about what it can do.
 */
export default function MovieRow({
  title,
  subtitle,
  items = [],
  loading = false,
  numbered = false,
  showMatch = false,
  action = null,
  priorityCount = 0,
}) {
  const scroller = useRef(null);
  const [atStart, setAtStart] = useState(true);
  const [atEnd, setAtEnd] = useState(false);

  const syncEdges = useCallback(() => {
    const node = scroller.current;
    if (!node) return;
    setAtStart(node.scrollLeft <= 4);
    setAtEnd(node.scrollLeft + node.clientWidth >= node.scrollWidth - 4);
  }, []);

  useEffect(() => {
    syncEdges();
    const node = scroller.current;
    if (!node) return undefined;

    // A ResizeObserver catches the case where the row becomes scrollable only
    // after images load or the window narrows.
    const observer = new ResizeObserver(syncEdges);
    observer.observe(node);
    return () => observer.disconnect();
  }, [syncEdges, items.length]);

  const scrollBy = (direction) => {
    const node = scroller.current;
    if (!node) return;
    node.scrollBy({ left: direction * node.clientWidth * 0.85, behavior: 'smooth' });
  };

  if (!loading && items.length === 0) return null;

  return (
    <section className="group/row relative">
      <div className="mb-3 flex items-end justify-between gap-4 px-1">
        <div className="min-w-0">
          <h2 className="truncate text-lg font-semibold tracking-snug text-white sm:text-xl">
            {title}
          </h2>
          {subtitle && <p className="mt-0.5 truncate text-sm text-white/45">{subtitle}</p>}
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {action}
          <div className="hidden items-center gap-1.5 sm:flex">
            <button
              type="button"
              onClick={() => scrollBy(-1)}
              disabled={atStart}
              aria-label={`Scroll ${title} left`}
              className="btn-icon disabled:opacity-25"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={() => scrollBy(1)}
              disabled={atEnd}
              aria-label={`Scroll ${title} right`}
              className="btn-icon disabled:opacity-25"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      <div ref={scroller} onScroll={syncEdges} className="scroll-row px-1">
        {loading
          ? Array.from({ length: 8 }, (_, index) => <CardSkeleton key={index} />)
          : items.map((movie, index) => (
              <MovieCard
                key={movie.id}
                movie={movie}
                rank={numbered ? index + 1 : null}
                matchScore={showMatch ? movie.matchScore ?? null : null}
                priority={index < priorityCount}
                className="w-[44vw] shrink-0 xs:w-[38vw] sm:w-[30vw] md:w-[22vw] lg:w-[15.5vw] xl:w-[12.5vw]"
              />
            ))}
      </div>
    </section>
  );
}
