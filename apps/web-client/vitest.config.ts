import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

/**
 * Separate from `vite.config.ts` so the unit suite never inherits the dev
 * proxy or the Tailwind plugin, and so `tests/e2e/` (Playwright, browser and
 * a running stack) cannot be picked up by `vitest` -- TDD 4A §11 requires
 * those to be different jobs precisely so one cannot mask the other.
 */
export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/unit/**/*.test.ts", "tests/unit/**/*.test.tsx"],
    exclude: ["tests/e2e/**"],
  },
});
