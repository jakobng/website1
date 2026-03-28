/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'gallery': {
          'base': '#FFFFFF',
          'surface': '#FAFAFA',
          'border': '#1A1A1A',
          'text': '#1A1A1A',
          'muted': '#737373',
          'accent': '#FF4D00', // Punchy "Safety Orange" for clarity/coolness
        }
      },
      fontFamily: {
        'sans': ['Inter', 'sans-serif'],
        'serif': ['Playfair Display', 'serif'],
        'mono': ['IBM Plex Mono', 'monospace'],
      },
      borderRadius: {
        'sm': '2px', // Very subtle rounding for a premium feel
      }
    },
  },
  plugins: [],
}
