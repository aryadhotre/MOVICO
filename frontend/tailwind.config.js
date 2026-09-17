/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Layered near-black surfaces with a cool cast, so translucent panels
        // read as glass rather than grey.
        ink: {
          950: '#06060A',
          900: '#0A0A11',
          850: '#0E0E17',
          800: '#13131E',
          750: '#191926',
          700: '#22222F',
        },
        violet: {
          400: '#A18BFF',
          500: '#8B6DFF',
          600: '#7C5CFF',
          700: '#6344E8',
        },
        magenta: {
          400: '#FF7AAC',
          500: '#FF4D8D',
          600: '#EC2E74',
        },
        amber: {
          400: '#FFC866',
          500: '#FFB84D',
        },
        mint: {
          400: '#5FE8AE',
          500: '#3DDC97',
        },
      },
      fontFamily: {
        sans: ['Inter var', 'Inter', 'system-ui', '-apple-system', 'sans-serif'],
        display: ['"Instrument Serif"', 'Georgia', 'serif'],
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
      },
      letterSpacing: {
        tightest: '-0.04em',
        snug: '-0.022em',
      },
      borderRadius: {
        '4xl': '2rem',
      },
      boxShadow: {
        glow: '0 0 40px -8px rgba(124, 92, 255, 0.45)',
        'glow-lg': '0 0 80px -12px rgba(124, 92, 255, 0.5)',
        card: '0 2px 8px rgba(0,0,0,0.4), 0 12px 32px -8px rgba(0,0,0,0.6)',
        lift: '0 8px 24px rgba(0,0,0,0.5), 0 24px 64px -16px rgba(124,92,255,0.35)',
      },
      backgroundImage: {
        'brand-gradient': 'linear-gradient(135deg, #7C5CFF 0%, #A855F7 45%, #FF4D8D 100%)',
        'brand-soft': 'linear-gradient(135deg, rgba(124,92,255,0.16), rgba(255,77,141,0.12))',
      },
      transitionTimingFunction: {
        // A single easing curve used everywhere, so motion feels like one system.
        smooth: 'cubic-bezier(0.22, 1, 0.36, 1)',
      },
      animation: {
        'fade-up': 'fadeUp 0.5s cubic-bezier(0.22,1,0.36,1) both',
        shimmer: 'shimmer 1.6s linear infinite',
        float: 'float 9s ease-in-out infinite',
        'spin-slow': 'spin 22s linear infinite',
      },
      keyframes: {
        fadeUp: {
          from: { opacity: '0', transform: 'translateY(12px)' },
          to: { opacity: '1', transform: 'none' },
        },
        shimmer: {
          '100%': { transform: 'translateX(100%)' },
        },
        float: {
          '0%, 100%': { transform: 'translate3d(0,0,0)' },
          '50%': { transform: 'translate3d(0,-18px,0)' },
        },
      },
      screens: {
        xs: '440px',
      },
    },
  },
  plugins: [],
};
