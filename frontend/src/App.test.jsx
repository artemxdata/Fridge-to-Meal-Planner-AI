// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App.jsx";

const responses = {
  "/api/v3/households/demo": {
    id: "demo-household",
    name: "Demo household",
    locale: "ru",
    created_at: "2026-06-08T00:00:00+00:00",
  },
  "/api/v3/households/demo-household/plans/accepted/latest": null,
  "/api/v3/households/demo-household/approval-events": [],
  "/api/v2/perception/parse": {
    items: [
      {
        name: "йогурт",
        quantity: 2,
        unit: "шт",
        confidence: 0.78,
        source: "receipt_text",
        reason: "matched product name",
      },
    ],
    raw_text: "Йогурт 2 шт",
    barcodes: [],
    needs_confirmation: true,
    fallback: "receipt_barcode_heuristics",
    notes: [],
  },
  "/api/v3/households/demo-household/observations": {
    id: "observation-1",
    household_id: "demo-household",
    source: "receipt",
    status: "pending",
    needs_confirmation: true,
    raw_payload: {},
    candidates: [
      {
        id: "candidate-1",
        session_id: "observation-1",
        household_id: "demo-household",
        ingredient_name: "йогурт",
        display_name: "йогурт",
        quantity: 2,
        unit: "шт",
        expires_in_days: null,
        source: "receipt_text",
        confidence: 0.78,
        reason: "matched product name",
        status: "pending",
        created_at: "2026-06-08T00:00:00+00:00",
        updated_at: "2026-06-08T00:00:00+00:00",
        confirmed_at: null,
      },
    ],
    created_at: "2026-06-08T00:00:00+00:00",
    updated_at: "2026-06-08T00:00:00+00:00",
  },
};

function mockFetch(url) {
  const parsed = new URL(url);
  const body = responses[parsed.pathname];
  if (!(parsed.pathname in responses)) {
    return Promise.resolve({
      ok: false,
      status: 404,
      text: () => Promise.resolve(JSON.stringify({ detail: `missing mock ${parsed.pathname}` })),
    });
  }
  return Promise.resolve({
    ok: true,
    status: 200,
    text: () => Promise.resolve(body === null ? "null" : JSON.stringify(body)),
  });
}

describe("React app", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal("fetch", vi.fn(mockFetch));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the human-controlled workspace and stores receipt candidates", async () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "Fridge-to-Meal Planner AI" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Perception" })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Household: Demo household")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Parse" }));

    await waitFor(() => {
      expect(screen.getAllByDisplayValue("йогурт").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText(/Stored observation: observation-1/)).toBeInTheDocument();
    });
  });
});
