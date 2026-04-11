import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "./App.jsx";

describe("Dashboard app", () => {
  it("renders command center by default", async () => {
    render(<App />);
    expect(
      await screen.findByRole("heading", { name: /Command Center/i }),
    ).toBeInTheDocument();
  });

  it("navigates to queue monitor", async () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /Queue Monitor/i }));
    expect(
      await screen.findByRole("heading", { name: /^Queue Monitor$/i }),
    ).toBeInTheDocument();
  });
});
