/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
    "./public/index.html"
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#5e2ca5',
          light: '#f4f0ff',
          dark: '#432078'
        },
        accent: '#ff7f0e',
        secondary: '#69b3a2',
        surface: '#faf8ff'
      }
    }
  },
  plugins: [require('@tailwindcss/forms')]
};