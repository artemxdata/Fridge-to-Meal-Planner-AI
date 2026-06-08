import { describe, expect, it } from "vitest";

import {
  buildPlanPayload,
  candidateConfirmations,
  companionTone,
  splitCsv,
} from "./domain";

describe("frontend domain helpers", () => {
  it("normalizes comma-separated values", () => {
    expect(splitCsv("eggs, milk, , onion")).toEqual(["eggs", "milk", "onion"]);
  });

  it("builds a v3 plan payload with visible policy", () => {
    const payload = buildPlanPayload({
      pantry: [{ name: "eggs", quantity: 2 }],
      form: {
        budget: "520",
        season: "",
        calories: "1800",
        protein: "95",
        contextNote: "warm food",
        allergies: "milk",
        disliked: "onion, garlic",
        maxCookingTime: "25",
        noShopMode: true,
        lowDishes: true,
        strictBudget: false,
      },
    });

    expect(payload.policy).toEqual({
      allergies: ["milk"],
      disliked_ingredients: ["onion", "garlic"],
      max_cooking_time_min: 25,
      no_shop_mode: true,
      low_dishes: true,
      strict_budget: false,
    });
    expect(payload.days).toBe(3);
  });

  it("maps selected observation candidates to confirmation payload", () => {
    expect(
      candidateConfirmations([
        {
          selected: true,
          observation_candidate_id: "candidate-1",
          name: "yogurt",
          quantity: 2,
          unit: "шт",
          confidence: 0.8,
        },
        { selected: false, observation_candidate_id: "candidate-2", name: "milk" },
      ]),
    ).toEqual([
      {
        candidate_id: "candidate-1",
        item: {
          name: "yogurt",
          quantity: 2,
          unit: "шт",
          expires_in_days: null,
          source: "human_confirmed_observation",
          confidence: 0.8,
        },
      },
    ]);
  });

  it("keeps companion tones predictable", () => {
    expect(companionTone("steady")).toBe("good");
    expect(companionTone("shopping_heavy")).toBe("action");
  });
});
