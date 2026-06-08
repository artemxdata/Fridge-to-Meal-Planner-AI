export function splitCsv(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function buildPolicy(form) {
  return {
    allergies: splitCsv(form.allergies),
    disliked_ingredients: splitCsv(form.disliked),
    max_cooking_time_min: form.maxCookingTime ? Number(form.maxCookingTime) : null,
    no_shop_mode: Boolean(form.noShopMode),
    low_dishes: Boolean(form.lowDishes),
    strict_budget: Boolean(form.strictBudget),
  };
}

export function buildPlanPayload({ pantry, form }) {
  return {
    pantry,
    budget_per_day: Number(form.budget || 520),
    season: form.season || null,
    target_calories: Number(form.calories || 1800),
    protein_goal_g: Number(form.protein || 95),
    meal_preference: "day",
    days: 3,
    context_note: form.contextNote || null,
    policy: buildPolicy(form),
  };
}

export function candidateConfirmations(candidates) {
  return candidates
    .filter((candidate) => candidate.selected)
    .map((candidate) => ({
      candidate_id: candidate.observation_candidate_id,
      item: {
        name: candidate.name,
        quantity: Number(candidate.quantity || 1),
        unit: candidate.unit || "pcs",
        expires_in_days: candidate.expires_in_days ?? null,
        source: "human_confirmed_observation",
        confidence: candidate.confidence ?? null,
      },
    }));
}

export function companionTone(state) {
  const map = {
    steady: "good",
    needs_protein: "watch",
    budget_watch: "watch",
    use_soon: "watch",
    shopping_heavy: "action",
    overloaded: "action",
  };
  return map[state] || "watch";
}

export function optionMetrics(option) {
  const totals = option?.plan?.totals || {};
  return [
    `${totals.calories || 0} kcal`,
    `${totals.protein_g || 0}g protein`,
    `${totals.cost || 0} rub`,
    `${option?.plan?.statistics?.pantry_usage_percent || 0}% pantry`,
  ];
}

export function buildPlanOverridePayload(option, note) {
  return {
    requested_change: note || "Review this draft before approval.",
    original_option_id: option.option_id,
    original_strategy: option.strategy,
    source: "react_demo_human_override",
  };
}

export function buildShoppingDecisionPayload({ acceptedPlanId, item, index, decision }) {
  const payload = {
    accepted_plan_id: acceptedPlanId,
    item_index: index,
    item_payload: item,
    decision,
    actor: "demo-user",
    reason:
      decision === "approved"
        ? "needed for approved meal plan"
        : decision === "skipped"
          ? "human chose to skip this shopping item"
          : "human changed this shopping item before buying",
  };

  if (decision === "changed") {
    payload.override_payload = {
      change_request: "adjust quantity or replace before purchase",
      original_item: item,
      source: "react_demo_shopping_override",
    };
  }

  return payload;
}
