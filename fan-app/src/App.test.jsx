import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "./App.jsx";

describe("Fan app", () => {
  it("renders the live best gate section", async () => {
    render(<App />);
    expect(await screen.findByText(/Best Gate/i)).toBeInTheDocument();
  });

  it("switches tabs from home to queues and alerts", async () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: /Queues/i }));
    expect(await screen.findByText(/^Gates$/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Alerts/i }));
    expect(await screen.findByText(/^No Notifications Yet$/i)).toBeInTheDocument();
  });
});
