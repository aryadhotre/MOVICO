import { useState } from 'react';
import { User } from 'lucide-react';
import { posterUrl } from '../lib/images';

function Portrait({ member }) {
  const [failed, setFailed] = useState(false);

  return (
    <li className="w-[104px] shrink-0">
      <div className="relative aspect-[2/3] overflow-hidden border border-print-100/10 bg-film-800">
        {member.profile_path && !failed ? (
          <img
            // Portraits are TMDB "profile" assets and share the poster size ladder;
            // w185 is the smallest that stays sharp at this width on a 2x display.
            src={posterUrl(member.profile_path, 185)}
            alt=""
            loading="lazy"
            decoding="async"
            onError={() => setFailed(true)}
            className="h-full w-full object-cover object-top grayscale transition-all duration-500 ease-reel hover:grayscale-0"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <User className="h-6 w-6 text-print-500/40" strokeWidth={1.4} />
          </div>
        )}
      </div>

      <p className="clamp-2 mt-2 font-display text-2xs uppercase leading-snug tracking-slate text-print-100">
        {member.name}
      </p>
      {member.character && (
        <p className="clamp-2 mt-1 font-mono text-[10px] leading-snug text-print-500">
          {member.character}
        </p>
      )}
    </li>
  );
}

/**
 * The billed cast, as a horizontal rail of portraits.
 *
 * Desaturated until hovered: a row of full-colour headshots from a dozen
 * different shoots is visually noisy and competes with the poster art, whereas
 * grayscale reads as one set and lets colour become the hover affordance.
 *
 * Falls back to the plain name list while the portrait backfill is still running,
 * so the section is never empty for a title that has cast data in text form.
 */
export default function CastRail({ billing = [], names = [] }) {
  if (billing.length === 0) {
    if (names.length === 0) return null;
    return (
      <section>
        <h2 className="slate-label mb-4">Cast</h2>
        <p className="text-sm leading-relaxed text-print-200">{names.join(' · ')}</p>
      </section>
    );
  }

  return (
    <section>
      <h2 className="slate-label mb-4">Cast</h2>
      <ul className="scroll-row" role="list">
        {billing.map((member) => (
          <Portrait key={`${member.name}-${member.character ?? ''}`} member={member} />
        ))}
      </ul>
    </section>
  );
}
