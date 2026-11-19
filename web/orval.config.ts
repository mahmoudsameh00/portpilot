import { defineConfig } from "orval";

// The typed client and runtime schemas (Frontend plan §7), generated from the API's committed OpenAPI snapshot.
// `npm run gen:api`; the CI checks the generated files have no diff.
export default defineConfig({
  client: {
    input: "../docs/api/openapi.json",
    output: {
      mode: "single",
      target: "src/api/generated/client.ts",
      client: "fetch",
      baseUrl: "",
      override: {
        mutator: { path: "src/api/mutator.ts", name: "apiFetch" },
        fetch: { includeHttpResponseReturnType: false },
      },
    },
  },
  zod: {
    input: "../docs/api/openapi.json",
    output: { mode: "single", target: "src/api/generated/zod.ts", client: "zod" },
  },
});
