import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import App from "./App.jsx";

describe("Dashboard reliability", () => {
  it("shows loading skeleton before data hydrates", async () => {
    render(<App />);
    expect(
      screen.getByRole("status", { name: /Loading dashboard data/i }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: /^Command Center$/i }),
    ).toBeInTheDocument();
  });

  it("falls back to polling mode when websocket is unavailable", async () => {
    render(<App />);

    expect(
      await screen.findByRole("heading", { name: /^Command Center$/i }),
    ).toBeInTheDocument();
    expect(await screen.findByText(/Backoff Polling/i)).toBeInTheDocument();
  });

  it("shows retry alert when backend is unavailable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 503,
        json: async () => ({}),
      })),
    );

    render(<App />);

    expect(
      await screen.findByText(/Cannot connect to backend/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Retry/i })).toBeInTheDocument();
  });
});
