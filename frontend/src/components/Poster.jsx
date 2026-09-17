import { useState } from 'react';
import { Film } from 'lucide-react';
import { posterPlaceholder, posterSrcSet, posterUrl } from '../lib/images';

/**
 * A poster image that loads fast and never reflows.
 *
 * Four things are doing the work:
 *
 * 1. **srcset + sizes** — the browser downloads the width it will actually paint.
 *    The previous card requested `w500` everywhere, so a 160px grid thumbnail
 *    pulled a 70KB image to display ~25KB worth of pixels.
 * 2. **A 92px blur-up placeholder** — 2-4KB, arrives almost immediately, and gives
 *    the card content instead of an empty rectangle.
 * 3. **`loading="lazy"` plus a fixed aspect ratio** — off-screen posters are never
 *    fetched, and the reserved box means no layout shift when they arrive.
 * 4. **`decoding="async"`** — decoding happens off the main thread, so a long row
 *    of posters does not stall scrolling.
 *
 * `priority` opts an above-the-fold image out of lazy loading and raises its fetch
 * priority, which is what keeps the hero from being the last thing to appear.
 */
export default function Poster({
  path,
  alt,
  className = '',
  sizes = '(max-width: 640px) 45vw, (max-width: 1024px) 30vw, 200px',
  maxWidth = 500,
  priority = false,
  rounded = '',
}) {
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);

  if (!path || failed) {
    return (
      <div
        className={`flex aspect-[2/3] w-full items-center justify-center bg-film-800 ${rounded} ${className}`}
        aria-label={alt ? `${alt} (no artwork available)` : 'No artwork available'}
      >
        <Film className="h-7 w-7 text-print-500/50" strokeWidth={1.5} />
      </div>
    );
  }

  return (
    <div className={`relative aspect-[2/3] w-full overflow-hidden bg-film-800 ${rounded} ${className}`}>
      {/* Blurred low-resolution stand-in, removed once the real image paints. */}
      {!loaded && (
        <img
          src={posterPlaceholder(path)}
          alt=""
          aria-hidden="true"
          className="absolute inset-0 h-full w-full scale-110 object-cover blur-xl"
        />
      )}
      <img
        src={posterUrl(path, Math.min(maxWidth, 342))}
        srcSet={posterSrcSet(path, maxWidth)}
        sizes={sizes}
        alt={alt}
        loading={priority ? 'eager' : 'lazy'}
        fetchpriority={priority ? 'high' : 'auto'}
        decoding="async"
        onLoad={() => setLoaded(true)}
        onError={() => setFailed(true)}
        className={`absolute inset-0 h-full w-full object-cover transition-opacity duration-500 ease-reel ${
          loaded ? 'opacity-100' : 'opacity-0'
        }`}
      />
    </div>
  );
}
