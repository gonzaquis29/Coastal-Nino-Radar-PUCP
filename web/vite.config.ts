import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// La API (python -m radar.app) sirve web/dist; en desarrollo, Vite reenvía /api a la API local.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://localhost:8000" } },
  build: { outDir: "dist", emptyOutDir: true, target: "es2020", modulePreload: { polyfill: false } },
  test: { environment: "jsdom", include: ["src/**/*.test.{ts,tsx}"], css: false },
});
