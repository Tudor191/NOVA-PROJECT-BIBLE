import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

export default tseslint.config(
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    plugins: { "react-hooks": reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "@typescript-eslint/consistent-type-imports": "error",
      // `ignoreRestSiblings` covers the omit idiom -- `const { [k]: _drop,
      // ...rest } = obj` -- where the discarded binding is the whole point.
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_", ignoreRestSiblings: true },
      ],
    },
  },
  {
    // The security boundary AC-2 turns on, enforced by the linter as well as
    // by `tests/unit/security-boundary.test.ts`. A direct bus client or a
    // raw engine URL in this application is not a style problem, it is the
    // architecture being violated (doc 09 §6, doc 11 §1).
    files: ["src/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          paths: [
            { name: "nats", message: "The browser must never speak to the bus. Use realtime/ -> ws-gateway." },
            { name: "nats.ws", message: "The browser must never speak to the bus. Use realtime/ -> ws-gateway." },
            { name: "socket.io-client", message: "ws-gateway speaks plain WebSocket; see realtime/client.ts." },
          ],
        },
      ],
    },
  },
);
