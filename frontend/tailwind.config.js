/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        display: ['"Bebas Neue"', 'sans-serif'],
        sans: ['Manrope', 'sans-serif']
      },
      colors: {
        background: '#0B0E14',
        accent: {
          primary: '#E8B84B',
          primaryHover: '#D4A33B',
          secondary: '#22D3EE',
          gold: '#E8B84B',
          goldHover: '#D4A33B',
          ai: '#8B5CF6',
          aiHover: '#3B82F6'
        },
        text: {
          primary: '#F3F4F6', // off-white
          secondary: '#9CA3AF' // gray
        },
        rating: '#FBBF24'
      }
    },
  },
  plugins: [],
}
