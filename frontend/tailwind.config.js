/** @type {import('tailwindcss').Config} */
const rgb = (v) => `rgb(var(${v}) / <alpha-value>)`;

export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: { DEFAULT: rgb("--bg"), soft: rgb("--bg-soft"), card: "var(--bg-card)" },
        line: "var(--line)",
        // "gold" is the themeable accent token (kept named gold across components)
        gold: { DEFAULT: rgb("--accent"), soft: rgb("--accent-soft"), deep: rgb("--accent-deep") },
        grape: { DEFAULT: rgb("--grape"), soft: rgb("--grape-soft") },
        emerald: { DEFAULT: rgb("--emerald"), soft: rgb("--emerald-soft") },
        danger: rgb("--danger"),
        warn: rgb("--warn"),
        ink: { DEFAULT: rgb("--ink"), soft: rgb("--ink-soft"), faint: rgb("--ink-faint") },
      },
      fontFamily: {
        sans: ["Sora", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      boxShadow: {
        glass: "0 8px 32px rgba(0,0,0,0.36)",
        glow: "0 0 26px rgb(var(--accent) / 0.28)",
      },
      backgroundImage: {
        "radial-fade":
          "radial-gradient(1200px 600px at 75% -10%, rgb(var(--grape) / 0.10), transparent), radial-gradient(900px 520px at 5% 110%, rgb(var(--accent) / 0.08), transparent)",
      },
      keyframes: {
        float: { "0%,100%": { transform: "translateY(0)" }, "50%": { transform: "translateY(-8px)" } },
        pulseDot: { "0%,100%": { opacity: "0.4", transform: "scale(1)" }, "50%": { opacity: "1", transform: "scale(1.6)" } },
      },
      animation: {
        float: "float 6s ease-in-out infinite",
        pulseDot: "pulseDot 2.4s ease-in-out infinite",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
