/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#0B0E14',
        accent: {
          primary: '#8B5CF6',
          primaryHover: '#3B82F6',
          secondary: '#22D3EE'
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
