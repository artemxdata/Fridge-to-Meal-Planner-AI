import { describe, expect, it } from "vitest";

import {
  buildPlanOverridePayload,
  buildPlanPayload,
  buildPurchasePayload,
  buildShoppingDecisionPayload,
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
          unit: "pcs",
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
          unit: "pcs",
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

  it("builds explicit human override payloads", () => {
    expect(
      buildPlanOverridePayload(
        { option_id: "balanced", strategy: "balanced" },
        "replace dinner with a faster option",
      ),
    ).toEqual({
      requested_change: "replace dinner with a faster option",
      original_option_id: "balanced",
      original_strategy: "balanced",
      source: "react_demo_human_override",
    });
  });

  it("adds override payload for changed shopping decisions", () => {
    const payload = buildShoppingDecisionPayload({
      acceptedPlanId: "plan-1",
      item: { name: "beans", missing_quantity: 1, unit: "can" },
      index: 2,
      decision: "changed",
    });

    expect(payload).toMatchObject({
      accepted_plan_id: "plan-1",
      item_index: 2,
      decision: "changed",
      reason: "human changed this shopping item before buying",
    });
    expect(payload.override_payload.original_item.name).toBe("beans");
  });

  it("builds purchase payload from accepted shopping list items", () => {
    const payload = buildPurchasePayload({
      acceptedPlan: { id: "accepted-1" },
      items: [
        { name: "milk", missing_quantity: 2, unit: "pcs" },
        { name: "beans", quantity: 1, unit: "can" },
      ],
    });

    expect(payload).toMatchObject({
      source: "shopping_list",
      accepted_plan_id: "accepted-1",
      reason: "confirmed shopping list purchase",
    });
    expect(payload.items).toEqual([
      { name: "milk", quantity: 2, unit: "pcs", source: "shopping_list", confidence: 1 },
      { name: "beans", quantity: 1, unit: "can", source: "shopping_list", confidence: 1 },
    ]);
  });
});
