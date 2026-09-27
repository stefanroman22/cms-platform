import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      // Guardrail L1: animation imports come from motion/react, never framer-motion.
      "no-restricted-imports": [
        "error",
        {
          paths: [{ name: "framer-motion", message: "Import from 'motion/react' instead." }],
          patterns: [{ group: ["framer-motion/*"], message: "Import from 'motion/react' instead." }],
        },
      ],
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
