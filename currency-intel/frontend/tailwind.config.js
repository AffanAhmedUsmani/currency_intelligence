/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          light: "#ffffff",
          dark: "#0b0f14",
        },
      },
    },
  },
  plugins: [],
};
