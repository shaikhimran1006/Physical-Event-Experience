import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import App from "./App.jsx";

describe("Fan app reliability", () => {
  it("shows loading state while data is resolving", async () => {
    render(<App />);
    expect(
      screen.getByRole("status", { name: /Loading fan app data/i }),
    ).toBeInTheDocument();
    expect(await screen.findByText(/Best Gate/i)).toBeInTheDocument();
  });

  it("keeps rendering recommendations when websocket is unavailable", async () => {
    render(<App />);

    expect(await screen.findByText(/Best Gate/i)).toBeInTheDocument();
  });

  it("renders retry alert on backend failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 503,
        json: async () => ({}),
      })),
    );

    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /Backend is not responding/i,
    );
  });
});
