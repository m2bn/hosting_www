import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        border: "#d9e0ea",
        surface: "#ffffff",
        muted: "#f5f7fb",
        ink: "#172033",
        subdued: "#667085",
        brand: {
          50: "#eef7ff",
          100: "#d7ebff",
          500: "#2563eb",
          600: "#1d4ed8",
          700: "#1e40af"
        },
        success: "#12805c",
        warning: "#b7791f",
        danger: "#c2410c"
      },
      boxShadow: {
        soft: "0 16px 40px rgba(23, 32, 51, 0.08)"
      }
    }
  },
  plugins: []
};

export default config;
