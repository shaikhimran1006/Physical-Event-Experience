import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";

import App from "./App.jsx";

describe("Dashboard accessibility", () => {
  it("has no critical accessibility violations", async () => {
    const { container } = render(<App />);
    await screen.findByRole("heading", { name: /^Command Center$/i });
    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });
});
