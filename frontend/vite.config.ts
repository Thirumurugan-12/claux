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
      // Frontend calls /api/*; Compose resolves `backend` on the shared network.
      "/api": {
        target: "http://backend:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
