import { useState } from 'react';
import { Star } from 'lucide-react';

/**
 * Half-star rating control over the API's 0.5-5.0 scale.
 *
 * Each star is split into two hit targets so half values are selectable by
 * pointer, and the whole control is keyboard operable via arrow keys. Rendering
 * the fill as a clipped overlay (rather than swapping icons) keeps the geometry
 * identical between empty, half and full, so nothing shifts as the value changes.
 */
export default function RatingStars({
  value = 0,
  onChange,
  size = 18,
  readOnly = false,
  showValue = false,
  className = '',
}) {
  const [preview, setPreview] = useState(null);
  const shown = preview ?? value ?? 0;

  const commit = (next) => {
    if (readOnly || !onChange) return;
    // Clicking the current value again clears it.
    onChange(next === value ? 0 : next);
  };

  const handleKeyDown = (event) => {
    if (readOnly || !onChange) return;
    if (event.key === 'ArrowRight' || event.key === 'ArrowUp') {
      event.preventDefault();
      onChange(Math.min(5, (value || 0) + 0.5));
    } else if (event.key === 'ArrowLeft' || event.key === 'ArrowDown') {
      event.preventDefault();
      onChange(Math.max(0, (value || 0) - 0.5));
    }
  };

  return (
    <div
      className={`inline-flex items-center gap-1.5 ${className}`}
      onMouseLeave={() => setPreview(null)}
    >
      <div
        className="flex items-center"
        role={readOnly ? 'img' : 'slider'}
        aria-label={readOnly ? `Rated ${value} out of 5` : 'Your rating'}
        aria-valuenow={readOnly ? undefined : value || 0}
        aria-valuemin={readOnly ? undefined : 0}
        aria-valuemax={readOnly ? undefined : 5}
        tabIndex={readOnly ? -1 : 0}
        onKeyDown={handleKeyDown}
      >
        {[1, 2, 3, 4, 5].map((star) => {
          const fill = Math.max(0, Math.min(1, shown - (star - 1)));
          return (
            <span key={star} className="relative block" style={{ width: size, height: size }}>
              <Star
                size={size}
                strokeWidth={1.6}
                className="absolute inset-0 text-print-100/20"
              />
              {fill > 0 && (
                <span
                  className="absolute inset-0 overflow-hidden"
                  style={{ width: `${fill * 100}%` }}
                >
                  <Star
                    size={size}
                    strokeWidth={1.6}
                    className="text-tungsten-500"
                    style={{ fill: 'currentColor' }}
                  />
                </span>
              )}

              {!readOnly && (
                <>
                  <button
                    type="button"
                    aria-label={`Rate ${star - 0.5} out of 5`}
                    className="absolute inset-y-0 left-0 w-1/2 cursor-pointer"
                    onMouseEnter={() => setPreview(star - 0.5)}
                    onClick={(event) => {
                      event.preventDefault();
                      event.stopPropagation();
                      commit(star - 0.5);
                    }}
                  />
                  <button
                    type="button"
                    aria-label={`Rate ${star} out of 5`}
                    className="absolute inset-y-0 right-0 w-1/2 cursor-pointer"
                    onMouseEnter={() => setPreview(star)}
                    onClick={(event) => {
                      event.preventDefault();
                      event.stopPropagation();
                      commit(star);
                    }}
                  />
                </>
              )}
            </span>
          );
        })}
      </div>

      {showValue && shown > 0 && (
        <span className="font-mono text-2xs tabular-nums text-print-300">
          {shown.toFixed(1)}
        </span>
      )}
    </div>
  );
}
