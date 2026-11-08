import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["skills/**/evals/vectors/*.test.ts"],
    environment: "node",
  },
});
