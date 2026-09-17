/**
 * A strip of 35mm sprocket holes.
 *
 * Used as a divider and as the edge of the filmstrip carousel. The proportions
 * follow real stock: four perforations per frame along each edge, with the hole
 * taller than it is wide (Kodak Standard / KS-1870).
 */
export default function Perforations({ orientation = 'horizontal', className = '' }) {
  const horizontal = orientation === 'horizontal';

  return (
    <div
      aria-hidden="true"
      className={`relative overflow-hidden bg-film-900 ${
        horizontal ? 'h-5 w-full' : 'h-full w-5'
      } ${className}`}
    >
      <div
        className={`absolute inset-0 ${horizontal ? 'perforated-x' : 'perforated-y'}`}
      />
      <div
        className={`absolute ${
          horizontal ? 'inset-x-0 top-0 h-px' : 'inset-y-0 left-0 w-px'
        } bg-print-100/15`}
      />
      <div
        className={`absolute ${
          horizontal ? 'inset-x-0 bottom-0 h-px' : 'inset-y-0 right-0 w-px'
        } bg-print-100/15`}
      />
    </div>
  );
}
