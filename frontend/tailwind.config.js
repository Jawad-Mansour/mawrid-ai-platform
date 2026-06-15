/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: "#0F1419",
          soft: "#141A22",
          card: "rgba(20,25,35,0.7)",
        },
        line: "rgba(212,163,115,0.14)",
        gold: { DEFAULT: "#D4A373", soft: "#E5C39E", deep: "#B07D4F" },
        emerald: { DEFAULT: "#2D6A4F", soft: "#40916C" },
        grape: { DEFAULT: "#9D4EDD", soft: "#B66EEE" },
        danger: "#E5484D",
        warn: "#E2A03F",
        ink: { DEFAULT: "#ECE7DF", soft: "#A7A294", faint: "#6B6759" },
      },
      fontFamily: {
        sans: ["Sora", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      boxShadow: {
        glass: "0 8px 32px rgba(0,0,0,0.36)",
        glow: "0 0 24px rgba(212,163,115,0.25)",
      },
      backgroundImage: {
        "radial-fade": "radial-gradient(1200px 600px at 70% -10%, rgba(157,78,221,0.10), transparent), radial-gradient(900px 500px at 10% 110%, rgba(212,163,115,0.08), transparent)",
      },
      keyframes: {
        float: { "0%,100%": { transform: "translateY(0)" }, "50%": { transform: "translateY(-8px)" } },
        pulseDot: { "0%,100%": { opacity: "0.4", transform: "scale(1)" }, "50%": { opacity: "1", transform: "scale(1.6)" } },
        shimmer: { "100%": { transform: "translateX(100%)" } },
      },
      animation: {
        float: "float 6s ease-in-out infinite",
        pulseDot: "pulseDot 2.4s ease-in-out infinite",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
