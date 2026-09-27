import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Surface tokens
        "s-base":    "var(--bg-base)",
        "s-surface": "var(--bg-surface)",
        "s-raised":  "var(--bg-raised)",
        // Border tokens
        "b-subtle":  "var(--border-subtle)",
        "b-active":  "var(--border-active)",
        // Text tokens
        "t-primary":   "var(--text-primary)",
        "t-secondary": "var(--text-secondary)",
        "t-dim":       "var(--text-dim)",
        // Semantic tokens
        "c-amber":   "var(--c-amber)",
        "c-green":   "var(--c-green)",
        "c-red":     "var(--c-red)",
      },
      fontFamily: {
        sans:  ["var(--font-geist-sans)", "system-ui", "sans-serif"],
        mono:  ["var(--font-geist-mono)", "Menlo", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};
export default config;
