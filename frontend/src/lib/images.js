/**
 * TMDB image URL construction.
 *
 * The API returns bare image paths and the client picks the size, which is the
 * whole reason posters load quickly now. Previously every image — including
 * 150px-wide grid thumbnails — was requested at `w500`, so a 24-card page pulled
 * roughly 24 x 70KB of poster art to render it at a third of that resolution.
 *
 * Serving a `srcset` lets the browser pick per device pixel ratio and viewport, so
 * a phone downloads `w185` where a Retina desktop takes `w500`.
 */

const CDN = 'https://image.tmdb.org/t/p';

/** Widths TMDB actually serves. Requesting anything else 404s. */
export const POSTER_WIDTHS = [92, 154, 185, 342, 500, 780];
export const BACKDROP_WIDTHS = [300, 780, 1280];

export function posterUrl(path, width = 342) {
  if (!path) return null;
  return `${CDN}/w${width}${path}`;
}

export function backdropUrl(path, width = 1280) {
  if (!path) return null;
  return `${CDN}/w${width}${path}`;
}

export function originalUrl(path) {
  if (!path) return null;
  return `${CDN}/original${path}`;
}

/**
 * Builds a srcset across the candidate widths at or below `max`.
 * Always keeps at least one entry so the attribute is never empty.
 */
export function posterSrcSet(path, max = 500) {
  if (!path) return undefined;
  const widths = POSTER_WIDTHS.filter((w) => w <= max);
  const chosen = widths.length ? widths : [POSTER_WIDTHS[0]];
  return chosen.map((w) => `${CDN}/w${w}${path} ${w}w`).join(', ');
}

export function backdropSrcSet(path) {
  if (!path) return undefined;
  return BACKDROP_WIDTHS.map((w) => `${CDN}/w${w}${path} ${w}w`).join(', ');
}

/**
 * The smallest poster TMDB serves, used as a blur-up placeholder.
 * At ~2-4KB it arrives almost immediately and gives the card something to show
 * other than an empty box while the full image decodes.
 */
export function posterPlaceholder(path) {
  if (!path) return null;
  return `${CDN}/w92${path}`;
}

export function youtubeThumb(key) {
  if (!key) return null;
  return `https://i.ytimg.com/vi/${key}/hqdefault.jpg`;
}

export function youtubeEmbed(key, { autoplay = true, mute = true } = {}) {
  if (!key) return null;
  const params = new URLSearchParams({
    autoplay: autoplay ? '1' : '0',
    mute: mute ? '1' : '0',
    controls: '1',
    rel: '0',
    modestbranding: '1',
    playsinline: '1',
  });
  return `https://www.youtube-nocookie.com/embed/${key}?${params}`;
}
