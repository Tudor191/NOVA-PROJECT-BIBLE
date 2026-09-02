import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

/**
 * `@nova/ui` and `@nova/nova-contracts` are workspace packages published as
 * TypeScript source with no build step. pnpm links them as real symlinks, so
 * Vite resolves them to paths outside `node_modules` and transforms them
 * like first-party source -- which is what makes `entities/` able to import
 * the generated contract types directly.
 *
 * The dev proxy exists so the browser only ever sees one origin. That is not
 * a convenience: the session cookie is `SameSite=Strict` (D-3), and doc 11
 * §1 requires every call to go through `api-gateway`. Talking to an engine
 * on another port in development would train the client to do in dev exactly
 * what the architecture forbids in production.
 */
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/v1": {
        target: process.env.NOVA_API_GATEWAY_URL ?? "http://localhost:8000",
        changeOrigin: true,
      },
      "/ws": {
        target: process.env.NOVA_WS_GATEWAY_URL ?? "http://localhost:8001",
        changeOrigin: true,
        ws: true,
        rewrite: (path) => path.replace(/^\/ws/, ""),
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
