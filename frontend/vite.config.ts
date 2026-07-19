import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    watch: {
      // Required for hot reload to work through a Docker bind mount on macOS.
      usePolling: true,
    },
    proxy: {
      // Frontend calls /api/*; the target is the backend. Compose resolves `backend` on the
      // shared network; set VITE_API_TARGET to the AppSail URL for a Catalyst deploy, or to
      // http://localhost:8000 for bare local dev.
      "/api": {
        target: process.env.VITE_API_TARGET ?? "http://backend:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
