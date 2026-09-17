/**
 * HTTP layer.
 *
 * The base URL is empty by default so requests go to the same origin. In
 * development Vite proxies /api to the backend, which removes a CORS preflight
 * from every request; in production VITE_API_URL points at the deployed API.
 * Hard-coding http://localhost:8005 (as the previous client did) meant the app
 * could never work anywhere but one machine.
 */

export const API_BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');

const TOKEN_KEY = 'movico.token';

/** Fired when a request is rejected as unauthenticated, so the app can sign out. */
export const AUTH_EXPIRED_EVENT = 'movico:auth-expired';

/**
 * Fired while the API is believed to be waking rather than broken, with
 * `detail.waking` true on the way in and false on the way out.
 *
 * The deployed API runs on a free instance that sleeps after 15 minutes of
 * inactivity and takes roughly 50 seconds to come back. Without this the first
 * visit of the day is indistinguishable from an outage: requests simply hang,
 * and whatever error eventually surfaces is wrong.
 */
export const API_WAKING_EVENT = 'movico:api-waking';

/**
 * `fetch` has no timeout of its own, so a request against a sleeping or
 * unreachable host hangs until the browser gives up -- minutes, on some
 * platforms. These bound it.
 *
 * The deployed budget is deliberately long. A cold Render instance legitimately
 * takes ~50s, and aborting at a conventional 10s would guarantee failure at
 * exactly the moment the app most needs to look reliable. Same-origin
 * development gets a short one, where a hang means a genuine bug.
 */
const REQUEST_TIMEOUT_MS = API_BASE ? 70_000 : 15_000;

/** How long a request may run before the UI is told the server is waking. */
const WAKING_AFTER_MS = 2_500;

/** A cold instance often refuses the very first connection outright. */
const NETWORK_RETRIES = 2;

let wakingDepth = 0;

function announceWaking(waking) {
  // Reference-counted: several requests fly in parallel on first paint, and the
  // banner should lift when the last of them lands, not the first.
  wakingDepth = Math.max(0, wakingDepth + (waking ? 1 : -1));
  const active = wakingDepth > 0;
  if (active === waking) {
    window.dispatchEvent(new CustomEvent(API_WAKING_EVENT, { detail: { waking: active } }));
  }
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export function getToken() {
  try {
    const raw = localStorage.getItem(TOKEN_KEY);
    // A literal "undefined"/"null" string is what a previous bug persisted, and it
    // produced "Authorization: Bearer undefined" on every call.
    if (!raw || raw === 'undefined' || raw === 'null') {
      if (raw) localStorage.removeItem(TOKEN_KEY);
      return null;
    }
    return raw;
  } catch {
    // Private mode or blocked storage.
    return null;
  }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable; the session simply will not persist */
  }
}

export class ApiError extends Error {
  constructor(message, status, payload) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.payload = payload;
  }
}

async function readError(response) {
  try {
    const body = await response.json();
    // The API returns a flattened string in `detail`; older shapes used an array.
    if (typeof body.detail === 'string') return body.detail;
    if (Array.isArray(body.detail)) {
      return body.detail.map((item) => item.msg || String(item)).join(', ');
    }
    return body.message || response.statusText;
  } catch {
    return response.statusText || `Request failed (${response.status})`;
  }
}

/**
 * Runs one fetch with a timeout, a waking signal and retries on network failure.
 *
 * The caller's own `signal` still cancels -- a component unmounting must abort
 * immediately, not wait out the timeout or trigger a retry -- so the two are
 * combined rather than replaced.
 */
async function fetchWithRecovery(url, init, callerSignal) {
  // One waking timer for the whole operation, not one per attempt. The wait the
  // user is sitting through is cumulative: two connections refused in 50ms each
  // plus their backoff is already two seconds, and a per-attempt timer would
  // restart from zero every time and so never fire.
  let announced = false;
  const wakingTimer = setTimeout(() => {
    announced = true;
    announceWaking(true);
  }, WAKING_AFTER_MS);

  try {
    for (let attempt = 0; attempt <= NETWORK_RETRIES; attempt += 1) {
      const controller = new AbortController();
      const onAbort = () => controller.abort();
      callerSignal?.addEventListener('abort', onAbort, { once: true });
      const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

      try {
        return await fetch(url, { ...init, signal: controller.signal });
      } catch (error) {
        // The caller cancelled: propagate untouched and never retry.
        if (callerSignal?.aborted) throw error;

        // A timeout is never retried. It already cost the full budget, and three
        // of them is nearly four minutes of the user watching nothing happen.
        // Only a *fast* failure is worth another go: a sleeping instance refuses
        // the first connection in milliseconds and accepts the next.
        const timedOut = controller.signal.aborted;
        if (timedOut || attempt === NETWORK_RETRIES) {
          throw new ApiError(
            timedOut
              ? 'The MOVICO API did not respond in time. It may still be waking up — try again in a moment.'
              : 'Cannot reach the MOVICO API. Check your connection and try again.',
            0,
            null,
          );
        }
        await sleep(600 * (attempt + 1));
      } finally {
        clearTimeout(timeout);
        callerSignal?.removeEventListener('abort', onAbort);
      }
    }
    // Unreachable: the final attempt either returns or throws above.
    throw new ApiError('Cannot reach the MOVICO API.', 0, null);
  } finally {
    clearTimeout(wakingTimer);
    if (announced) announceWaking(false);
  }
}

/**
 * Performs an API request.
 *
 * @param {string} path      path beginning with /api
 * @param {object} options   fetch options, plus `signal` for cancellation
 */
export async function apiFetch(path, options = {}) {
  const { body, headers: extraHeaders, form, ...rest } = options;
  const token = getToken();

  const headers = {
    Accept: 'application/json',
    ...(form ? {} : { 'Content-Type': 'application/json' }),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extraHeaders,
  };

  const payload = form ?? (body !== undefined ? JSON.stringify(body) : undefined);
  const response = await fetchWithRecovery(`${API_BASE}${path}`, {
    ...rest,
    headers,
    body: payload,
  }, rest.signal);

  if (response.status === 401) {
    // Never sign the user out because a login attempt was wrong.
    if (!path.includes('/auth/login') && !path.includes('/auth/register')) {
      setToken(null);
      window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT));
    }
    throw new ApiError(await readError(response), 401, null);
  }

  if (!response.ok) {
    throw new ApiError(await readError(response), response.status, null);
  }

  if (response.status === 204) return null;
  return response.json();
}

function query(params) {
  const search = new URLSearchParams();
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return;
    search.set(key, String(value));
  });
  const encoded = search.toString();
  return encoded ? `?${encoded}` : '';
}

/* ------------------------------------------------------------------ endpoints */

export const auth = {
  register: (payload) => apiFetch('/api/auth/register', { method: 'POST', body: payload }),
  login: (username, password) =>
    apiFetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      form: new URLSearchParams({ username, password }).toString(),
    }),
  me: (signal) => apiFetch('/api/auth/me', { signal }),
};

export const movies = {
  home: (signal) => apiFetch('/api/movies/home', { signal }),
  browse: (params, signal) => apiFetch(`/api/movies/browse${query(params)}`, { signal }),
  trending: (params, signal) => apiFetch(`/api/movies/trending${query(params)}`, { signal }),
  search: (params, signal) => apiFetch(`/api/movies/search${query(params)}`, { signal }),
  genres: (signal) => apiFetch('/api/movies/genres', { signal }),
  detail: (id, signal) => apiFetch(`/api/movies/${id}`, { signal }),
  similar: (id, limit = 12, signal) =>
    apiFetch(`/api/movies/${id}/similar${query({ limit })}`, { signal }),
};

export const ratings = {
  submit: (movieId, rating) =>
    apiFetch('/api/ratings', { method: 'POST', body: { movie_id: movieId, rating } }),
  submitBatch: (items) => apiFetch('/api/ratings/batch', { method: 'POST', body: items }),
  remove: (movieId) => apiFetch(`/api/ratings/${movieId}`, { method: 'DELETE' }),
  mine: (signal) => apiFetch('/api/ratings/mine', { signal }),
  history: (params, signal) => apiFetch(`/api/ratings/history${query(params)}`, { signal }),
  stats: (signal) => apiFetch('/api/ratings/stats', { signal }),
};

export const watchlist = {
  add: (movieId) =>
    apiFetch('/api/ratings/watchlist', { method: 'POST', body: { movie_id: movieId } }),
  remove: (movieId) => apiFetch(`/api/ratings/watchlist/${movieId}`, { method: 'DELETE' }),
  list: (params, signal) => apiFetch(`/api/ratings/watchlist${query(params)}`, { signal }),
  ids: (signal) => apiFetch('/api/ratings/watchlist/ids', { signal }),
};

export const recommendations = {
  get: (params, signal) => apiFetch(`/api/recommendations${query(params)}`, { signal }),
};

export const system = {
  health: (signal) => apiFetch('/api/system/health', { signal }),
  stats: (signal) => apiFetch('/api/system/stats', { signal }),
  metrics: (signal) => apiFetch('/api/system/metrics', { signal }),
};
