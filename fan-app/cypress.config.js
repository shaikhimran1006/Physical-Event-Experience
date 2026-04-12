import { defineConfig } from "cypress";

export default defineConfig({
  e2e: {
    baseUrl: "http://localhost:5174",
    specPattern: "cypress/e2e/**/*.cy.js",
  },
});
