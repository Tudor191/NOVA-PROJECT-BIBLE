import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

/**
 * `@nova/ui` and `@nova/nova-contracts` are workspace packages published as
 * TypeScript source with no build step. pnpm links them as real symlinks, so
 * Vite resolves them to paths outside `node_modules` and transforms them
 * like first-party source -- which is what makes `entities/` able to import
 * the generated contract types directly.
 */

/**
 * One origin, in every mode.
 *
 * This is not a convenience. The session cookie is `SameSite=Strict` (D-3),
 * so a cross-origin call would simply not carry it and every request would
 * come back 401 -- which is exactly what happened the first time the E2E job
 * was wired to point `VITE_API_GATEWAY_URL` at a different port. Doc 11 §1
 * also requires every call to go through `api-gateway`; talking to a
 * different origin in development or in CI would train the client to do what
 * the architecture forbids in production.
 *
 * Applied to `preview` as well as `server` so the Playwright run exercises
 * the same single-origin shape as a real deployment rather than a special
 * case that only exists in CI.
 */
const proxy = {
  "/v1": {
    target: process.env.NOVA_API_GATEWAY_URL ?? "http://localhost:8000",
    changeOrigin: true,
  },
  "/ws": {
    target: process.env.NOVA_WS_GATEWAY_URL ?? "http://localhost:8001",
    changeOrigin: true,
    ws: true,
    rewrite: (path: string) => path.replace(/^\/ws/, ""),
  },
} as const;

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, proxy },
  // `host` and `strictPort` are explicit because Playwright polls
  // `http://127.0.0.1:4173` literally. Vite's default host is `localhost`,
  // which resolves to `::1` before `127.0.0.1` on the GitHub runners -- the
  // server comes up on IPv6, the poll never connects, and the run dies with
  // "Timed out waiting 120000ms from config.webServer" having executed no
  // tests at all. Binding the same literal address Playwright dials removes
  // the ambiguity; `strictPort` makes a port clash fail loudly instead of
  // silently serving somewhere else.
  preview: { port: 4173, strictPort: true, host: "127.0.0.1", proxy },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
