/** @type {import('tailwindcss').Config} */

/**
 * Design language: "Projection".
 *
 * Built from film-projection vocabulary rather than generic product-UI gradients.
 *
 * Colour: film black is warm, not blue-black, so the surfaces carry a brown cast.
 * The accents are the two colours cinema actually runs on — tungsten amber (the
 * projector bulb, ~3200K) and negative teal. That pairing is the "teal and orange"
 * grade practically every modern film is finished in, used here deliberately.
 *
 * Type: Jost is a Futura revival. Futura is the closest thing cinema has to a
 * house typeface — Kubrick used it almost exclusively, Wes Anderson still does,
 * and it set the Alien titles. JetBrains Mono carries the technical metadata
 * (timecodes, aspect ratios, reel identifiers) the way a camera report would.
 */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Warm blacks, graded like a film print rather than a UI dark mode.
        film: {
          950: '#0A0908',
          900: '#100E0C',
          850: '#171412',
          800: '#1F1B18',
          750: '#292420',
          700: '#38312B',
          600: '#4A423A',
        },
        // Projector bulb. The primary accent.
        tungsten: {
          200: '#FBE3B8',
          300: '#F7CE85',
          400: '#F3B857',
          500: '#EDA32C',
          600: '#D4881A',
          700: '#A96812',
        },
        // The cool half of the grade.
        negative: {
          300: '#8FE3D8',
          400: '#5BCFC1',
          500: '#33B8A8',
          600: '#219588',
        },
        // Reserved for ratings, alerts and the record light.
        reel: {
          400: '#F0564B',
          500: '#E03C31',
          600: '#BE2C22',
        },
        // Print white is cream, never #FFF.
        print: {
          50: '#FAF7F2',
          100: '#F2ECE2',
          200: '#DED5C8',
          300: '#B5AA9B',
          400: '#8A8075',
          500: '#635C54',
        },
      },
      fontFamily: {
        // Futura revival — the display voice.
        display: ['Jost', 'Futura', 'Century Gothic', 'sans-serif'],
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
      },
      letterSpacing: {
        // Title-card spacing: wide tracking on uppercase display type.
        marquee: '0.28em',
        slate: '0.16em',
        tightest: '-0.045em',
      },
      boxShadow: {
        // Halation: the warm bloom light leaves around bright areas on film stock.
        halate: '0 0 60px -12px rgba(237, 163, 44, 0.45)',
        'halate-lg': '0 0 110px -18px rgba(237, 163, 44, 0.55)',
        print: '0 1px 2px rgba(0,0,0,0.6), 0 12px 28px -10px rgba(0,0,0,0.75)',
        lift: '0 8px 20px rgba(0,0,0,0.55), 0 30px 70px -20px rgba(0,0,0,0.8)',
      },
      backgroundImage: {
        // Sprocket holes down the edge of a 35mm strip.
        perf: 'repeating-linear-gradient(to bottom, transparent 0 10px, rgba(250,247,242,0.16) 10px 22px)',
        'perf-x': 'repeating-linear-gradient(to right, transparent 0 10px, rgba(250,247,242,0.16) 10px 22px)',
        // Clapperboard.
        slate: 'repeating-linear-gradient(115deg, #FAF7F2 0 14px, #100E0C 14px 28px)',
      },
      transitionTimingFunction: {
        // One curve everywhere, so motion reads as a single mechanism.
        reel: 'cubic-bezier(0.22, 1, 0.36, 1)',
        gate: 'cubic-bezier(0.83, 0, 0.17, 1)',
      },
      animation: {
        'leader-sweep': 'leaderSweep 1s linear infinite',
        'cue-burn': 'cueBurn 14s ease-in-out infinite',
        'gate-open': 'gateOpen 1.1s cubic-bezier(0.83,0,0.17,1) both',
        'slow-zoom': 'slowZoom 26s ease-out both',
        flicker: 'flicker 5s steps(1) infinite',
        shimmer: 'shimmer 1.8s linear infinite',
        'rise-in': 'riseIn 0.7s cubic-bezier(0.22,1,0.36,1) both',
      },
      keyframes: {
        // The rotating hand of an Academy countdown leader.
        leaderSweep: { to: { transform: 'rotate(360deg)' } },
        // A cue mark: two burns, the warning then the change-over.
        cueBurn: {
          '0%, 91%': { opacity: '0' },
          '92%, 93.5%': { opacity: '0.9' },
          '94%, 95.5%': { opacity: '0' },
          '96%, 97.5%': { opacity: '0.9' },
          '98%, 100%': { opacity: '0' },
        },
        // Letterbox bars pulling back like a projector gate opening.
        gateOpen: {
          from: { transform: 'scaleY(1)' },
          to: { transform: 'scaleY(0)' },
        },
        slowZoom: {
          from: { transform: 'scale(1.12)' },
          to: { transform: 'scale(1)' },
        },
        // Tungsten bulbs are never perfectly steady.
        flicker: {
          '0%, 96%, 100%': { opacity: '1' },
          '97%': { opacity: '0.82' },
          '98%': { opacity: '1' },
          '99%': { opacity: '0.9' },
        },
        shimmer: { '100%': { transform: 'translateX(100%)' } },
        riseIn: {
          from: { opacity: '0', transform: 'translateY(18px)' },
          to: { opacity: '1', transform: 'none' },
        },
      },
      screens: {
        xs: '440px',
      },
    },
  },
  plugins: [],
};
