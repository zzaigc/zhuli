import animate from "tailwindcss-animate";

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Montserrat", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      colors: {
        ink: {
          900: "#0B1120",
          800: "#111827",
          700: "#1E293B",
        },
        neon: {
          cyan: "#22D3EE",
          blue: "#3B82F6",
          indigo: "#6366F1",
        },
        func: {
          green: "#22C55E",
          red: "#EF4444",
          amber: "#F59E0B",
        },
      },
      boxShadow: {
        glow: "0 0 24px rgba(34,211,238,0.25)",
        "glow-strong": "0 0 36px rgba(34,211,238,0.45)",
      },
      keyframes: {
        pulseRing: {
          "0%,100%": { opacity: "0.6" },
          "50%": { opacity: "1" },
        },
        floatIn: {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        scan: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(400%)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        bees: {
          "0%,100%": { transform: "translate(0,0) scale(1)", opacity: "0.7" },
          "50%": { transform: "translate(4px,-6px) scale(1.15)", opacity: "1" },
        },
      },
      animation: {
        pulseRing: "pulseRing 2s ease-in-out infinite",
        floatIn: "floatIn 0.35s ease-out",
        scan: "scan 3.5s linear infinite",
        shimmer: "shimmer 2.5s linear infinite",
        bees: "bees 1.8s ease-in-out infinite",
      },
    },
  },
  plugins: [animate],
};
