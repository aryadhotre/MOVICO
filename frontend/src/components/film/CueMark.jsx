/**
 * A cue mark — the "cigarette burn" a projectionist watched for.
 *
 * On a release print these were scratched or punched into the top-right corner of
 * the frame in pairs: the first appeared about eight seconds before the end of a
 * reel as a warning, the second a few frames before the splice, as the signal to
 * change over to the second projector. Fight Club is why most people know them.
 *
 * Reproduced faithfully: top-right, two burns a beat apart, on a long cycle so it
 * reads as an artefact of the medium rather than a UI animation. Purely
 * decorative, so it is hidden from assistive technology and does not animate for
 * anyone who has asked for reduced motion.
 */
export default function CueMark({ className = '' }) {
  return (
    <div
      aria-hidden="true"
      className={`pointer-events-none absolute right-[4%] top-[7%] z-20 motion-reduce:hidden ${className}`}
    >
      <span className="block h-11 w-11 animate-cue-burn rounded-full bg-[radial-gradient(circle,rgba(250,247,242,0.9)_0%,rgba(237,163,44,0.55)_38%,transparent_68%)] blur-[1px]" />
    </div>
  );
}
