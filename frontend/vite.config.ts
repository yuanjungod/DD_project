import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

/** Dev server proxies /api → backend so the browser avoids CORS and hard-coded ports. */
const backendTarget =
  typeof process.env.VITE_DEV_PROXY_TARGET === "string" &&
  process.env.VITE_DEV_PROXY_TARGET.trim() !== ""
    ? process.env.VITE_DEV_PROXY_TARGET.trim()
    : "http://127.0.0.1:8010";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: backendTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
