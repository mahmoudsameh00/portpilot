import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

// Logical direction utilities in our code (ms-/me-/ps-/pe-/start-/end-/text-start): answers can be Arabic (dir=auto).
const PHYSICAL =
  "/(^|[\s:\"'`])-?(ml|mr|pl|pr|left|right|border-l|border-r|rounded-l|rounded-r|rounded-tl|rounded-tr|rounded-bl|rounded-br|text-left|text-right|float-left|float-right|scroll-ml|scroll-mr)-/";

export default defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      "react/no-danger": "error", // model text is never HTML (plan §4.5)
      "@typescript-eslint/no-explicit-any": "error",
      "no-restricted-syntax": [
        "error",
        {
          selector: `Literal[value=${PHYSICAL}]`,
          message: "Physical direction class: use a logical one (RTL, plan §8).",
        },
        {
          selector: `TemplateElement[value.raw=${PHYSICAL}]`,
          message: "Physical direction class: use a logical one (RTL, plan §8).",
        },
      ],
    },
  },
  {
    // shadcn/ui copies keep their upstream classes; the interface is English / LTR (D-FE-6), the ban guards our code.
    files: ["src/components/ui/**"],
    rules: { "no-restricted-syntax": "off" },
  },
  globalIgnores([
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    "playwright-report/**",
    "test-results/**",
  ]),
]);
