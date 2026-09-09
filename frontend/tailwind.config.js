/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        slate: {
          50: '#f8fafc',
          100: '#f1f5f9',
          200: '#e2e8f0',
          300: '#cbd5e1',
          700: '#334155',
          800: '#1e293b',
          900: '#0f172a',
        },
        sky: {
          500: '#0ea5e9',
          600: '#0284c7',
        }
      },
      fontFamily: { sans: ['Inter','system-ui','sans-serif'] }
    },
  },
  plugins: [],
}
