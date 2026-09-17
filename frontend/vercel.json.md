# Notes on `vercel.json`

Plain JSON has no comment syntax, and Vercel's schema validator rejects unknown
properties (including a `comment` key) inside `rewrites`/`headers` entries — that
config must be exactly what Vercel expects, nothing more. This file holds the
rationale that would otherwise live inline.

### `rewrites`
Client-side routing: every unmatched path must serve the SPA shell, otherwise a
deep link like `/movie/318` 404s on refresh.

### `headers` — caching
- `/assets/(.*)` — hashed filenames change whenever content changes, so they can
  be cached permanently (`immutable`).
- `/` — `index.html` must never be cached: it names the hashed asset files, so a
  stale copy points at bundles that no longer exist.

### `headers` — security, applied to everything (`/(.*)`)
Standard hardening headers (`X-Content-Type-Options`, `X-Frame-Options`,
`Referrer-Policy`, `Permissions-Policy`, `Strict-Transport-Security`).

**`Content-Security-Policy`** enumerates exactly what the app loads: TMDB
artwork, YouTube trailer embeds and their thumbnails, Google Fonts, and the API.
`'unsafe-inline'` is present for **styles only**, because Tailwind's
runtime-injected styles and Framer Motion's animated style attributes require
it; scripts have no such exemption, which is the half that actually stops an
injected `<script>` from running. `connect-src` is intentionally broad on
`https:` so pointing `VITE_API_URL` at a different backend does not silently
break every request.

If you change what the frontend loads from (a new image CDN, a different embed
provider), update the CSP here to match — a resource silently blocked by CSP
looks like a network failure, not a policy violation, in the browser console
unless you check for CSP warnings specifically.
