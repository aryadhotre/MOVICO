/**
 * Formatting in the vocabulary of a camera report.
 *
 * Presenting a runtime as "01:48:00" rather than "1h 48m" is a small thing that
 * does a lot of work: it is how every editor, assistant and projectionist writes
 * a duration, and it makes the metadata read as belonging to film rather than to
 * a generic media app.
 */

/** SMPTE-style timecode, HH:MM:SS, from a runtime in minutes. */
export function timecode(minutes) {
  if (!minutes || minutes <= 0) return null;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return `${String(hours).padStart(2, '0')}:${String(mins).padStart(2, '0')}:00`;
}

/** Plain-language runtime, for places where a timecode would be needlessly opaque. */
export function runtime(minutes) {
  if (!minutes || minutes <= 0) return null;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return hours ? `${hours}h ${mins}m` : `${mins}m`;
}

/**
 * The aspect ratio a film of this era and kind was most likely finished in.
 *
 * Inferred rather than stored: TMDB does not expose the ratio, but the
 * conventions are strong enough that era plus format gives the right answer most
 * of the time. Flagged as an inference wherever it is shown.
 */
export function inferAspectRatio(year, genres = []) {
  if (!year) return '1.85 : 1';
  // Before CinemaScope, essentially everything was Academy ratio.
  if (year < 1953) return '1.37 : 1';
  const epic = genres.some((genre) =>
    ['Sci-Fi', 'Adventure', 'Action', 'War', 'Western'].includes(genre),
  );
  // Anamorphic scope has been the default for spectacle since the mid-fifties.
  return epic ? '2.39 : 1' : '1.85 : 1';
}

/** Compact counts: 12345 -> "12.3K". */
export function compact(value) {
  if (value === null || value === undefined) return null;
  const number = Number(value);
  if (!Number.isFinite(number)) return null;
  if (number >= 1_000_000) return `${(number / 1_000_000).toFixed(number >= 10_000_000 ? 0 : 1)}M`;
  if (number >= 1_000) return `${(number / 1_000).toFixed(number >= 10_000 ? 0 : 1)}K`;
  return String(number);
}

/** A reel-style identifier, so every title carries a plausible print number. */
export function reelCode(id) {
  return `R${String(id).padStart(6, '0')}`;
}

/** Release decade as an era label. */
export function era(year) {
  if (!year) return null;
  return `${Math.floor(year / 10) * 10}s`;
}

export function languageName(code) {
  if (!code) return null;
  try {
    return new Intl.DisplayNames(['en'], { type: 'language' }).of(code);
  } catch {
    return code.toUpperCase();
  }
}
