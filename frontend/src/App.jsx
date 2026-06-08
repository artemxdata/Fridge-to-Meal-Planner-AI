import Activity from "lucide-react/dist/esm/icons/activity.js";
import Camera from "lucide-react/dist/esm/icons/camera.js";
import Check from "lucide-react/dist/esm/icons/check.js";
import ClipboardCheck from "lucide-react/dist/esm/icons/clipboard-check.js";
import Database from "lucide-react/dist/esm/icons/database.js";
import ListChecks from "lucide-react/dist/esm/icons/list-checks.js";
import RefreshCw from "lucide-react/dist/esm/icons/refresh-cw.js";
import Save from "lucide-react/dist/esm/icons/save.js";
import ScanLine from "lucide-react/dist/esm/icons/scan-line.js";
import ShoppingBasket from "lucide-react/dist/esm/icons/shopping-basket.js";
import Sparkles from "lucide-react/dist/esm/icons/sparkles.js";
import X from "lucide-react/dist/esm/icons/x.js";
import React from "react";
import { useEffect, useMemo, useState } from "react";

import {
  buildPlanPayload,
  candidateConfirmations,
  companionTone,
  optionMetrics,
  splitCsv,
} from "./domain";

const DEFAULT_API = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

const initialForm = {
  budget: "520",
  season: "",
  calories: "1800",
  protein: "95",
  contextNote: "I am tired and want warm food without shopping and with low cleanup",
  allergies: "",
  disliked: "",
  maxCookingTime: "",
  noShopMode: false,
  lowDishes: false,
  strictBudget: false,
};

function emptyPantryItem() {
  return {
    name: "",
    quantity: 1,
    unit: "шт",
    expires_in_days: 7,
    source: "manual",
    confidence: 1,
  };
}

function loadLocalPantry() {
  try {
    return JSON.parse(localStorage.getItem("ftm_react_pantry") || "[]");
  } catch {
    return [];
  }
}

function Pill({ children, tone = "neutral" }) {
  return <span className={`pill ${tone}`}>{children}</span>;
}

function IconButton({ icon: Icon, children, className = "", ...props }) {
  return (
    <button className={className} type="button" {...props}>
      <Icon size={17} />
      <span>{children}</span>
    </button>
  );
}

function Metric({ label, value }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <b>{value}</b>
    </div>
  );
}

function App() {
  const [apiBase, setApiBase] = useState(localStorage.getItem("ftm_api_base") || DEFAULT_API);
  const [householdId, setHouseholdId] = useState("");
  const [pantry, setPantry] = useState(loadLocalPantry);
  const [candidates, setCandidates] = useState([]);
  const [observationSessionId, setObservationSessionId] = useState("");
  const [planOptions, setPlanOptions] = useState([]);
  const [acceptedPlan, setAcceptedPlan] = useState(null);
  const [events, setEvents] = useState([]);
  const [companion, setCompanion] = useState(null);
  const [form, setForm] = useState(initialForm);
  const [receiptText, setReceiptText] = useState("Йогурт 2 шт\nКартофель 3 кг\nЯйца 10 шт");
  const [barcodeText, setBarcodeText] = useState("4600000000011");
  const [photoFile, setPhotoFile] = useState(null);
  const [textHint, setTextHint] = useState("яйца, йогурт, картофель");
  const [status, setStatus] = useState({
    workspace: "",
    perception: "No candidates yet.",
    plan: "Generate draft options to compare strategies.",
    accepted: "No accepted plan yet.",
    context: "",
    companion: "Generate a draft plan to update the companion.",
  });

  const metrics = useMemo(
    () => ({
      household: householdId || "-",
      pantry: pantry.length,
      options: planOptions.length,
      accepted: acceptedPlan?.status || "-",
    }),
    [acceptedPlan, householdId, pantry.length, planOptions.length],
  );

  useEffect(() => {
    localStorage.setItem("ftm_api_base", apiBase);
  }, [apiBase]);

  useEffect(() => {
    localStorage.setItem("ftm_react_pantry", JSON.stringify(pantry));
  }, [pantry]);

  useEffect(() => {
    if (!pantry.length) {
      setPantry([
        { name: "яйца", quantity: 4, unit: "шт", expires_in_days: 5, source: "sample", confidence: 1 },
        { name: "йогурт", quantity: 2, unit: "шт", expires_in_days: 3, source: "sample", confidence: 1 },
        { name: "картофель", quantity: 3, unit: "шт", expires_in_days: 12, source: "sample", confidence: 1 },
      ]);
    }
    loadHousehold();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function setStatusKey(key, value) {
    setStatus((current) => ({ ...current, [key]: value }));
  }

  async function api(path, options = {}) {
    const response = await fetch(`${apiBase.replace(/\/$/, "")}${path}`, options);
    const text = await response.text();
    const data = text ? JSON.parse(text) : null;
    if (!response.ok) {
      throw new Error(data?.detail || `HTTP ${response.status}`);
    }
    return data;
  }

  async function loadHousehold() {
    try {
      const household = await api("/api/v3/households/demo");
      setHouseholdId(household.id);
      setStatusKey("workspace", `Household: ${household.name}`);
      await Promise.all([loadAcceptedPlan(household.id), loadApprovalEvents(household.id)]);
      return household.id;
    } catch (error) {
      setStatusKey("workspace", error.message);
      return "";
    }
  }

  async function loadDemo() {
    try {
      const demo = await api("/api/v2/demo");
      setPantry(demo.pantry || []);
      setForm((current) => ({
        ...current,
        budget: String(demo.preferences?.budget_per_day || 520),
        season: demo.preferences?.season || "",
        calories: String(demo.preferences?.target_calories || 1800),
        protein: String(demo.preferences?.protein_goal_g || 95),
      }));
      const id = await loadHousehold();
      setStatusKey("workspace", `${demo.scenario || "Demo loaded."} ${id ? `(${id})` : ""}`);
    } catch (error) {
      setStatusKey("workspace", error.message);
    }
  }

  async function loadApprovalEvents(id = householdId) {
    if (!id) return;
    try {
      const data = await api(`/api/v3/households/${id}/approval-events`);
      setEvents(data || []);
    } catch (error) {
      setStatusKey("workspace", error.message);
    }
  }

  async function loadAcceptedPlan(id = householdId) {
    if (!id) return;
    try {
      const data = await api(`/api/v3/households/${id}/plans/accepted/latest`);
      setAcceptedPlan(data);
      if (data?.plan_payload) {
        await refreshCompanion(data.plan_payload);
      }
    } catch (error) {
      setStatusKey("accepted", error.message);
    }
  }

  function updatePantry(index, key, value) {
    setPantry((items) =>
      items.map((item, itemIndex) => (itemIndex === index ? { ...item, [key]: value } : item)),
    );
  }

  function updateCandidate(index, key, value) {
    setCandidates((items) =>
      items.map((item, itemIndex) => (itemIndex === index ? { ...item, [key]: value } : item)),
    );
  }

  async function storeObservation(source, items, rawPayload) {
    if (!items.length) return { items, observationId: "" };
    const id = householdId || (await loadHousehold());
    if (!id) return { items, observationId: "" };

    const observation = await api(`/api/v3/households/${id}/observations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source,
        actor: "demo-user",
        reason: "stored react perception candidates",
        candidates: items,
        raw_payload: rawPayload,
      }),
    });

    return {
      observationId: observation.id,
      items: items.map((item, index) => ({
        ...item,
        selected: true,
        observation_candidate_id: observation.candidates?.[index]?.id || "",
      })),
    };
  }

  async function parseReceipt() {
    try {
      setStatusKey("perception", "Parsing receipt and barcodes...");
      const data = await api("/api/v2/perception/parse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source: "receipt",
          raw_text: receiptText,
          barcodes: splitCsv(barcodeText),
        }),
      });
      const items = data.items || [];
      const stored = await storeObservation("receipt", items, {
        fallback: data.fallback,
        notes: data.notes,
        raw_text: data.raw_text,
        barcodes: data.barcodes,
      });
      setObservationSessionId(stored.observationId);
      setCandidates(stored.items);
      setStatusKey(
        "perception",
        `Candidates: ${stored.items.length}. needs_confirmation=${data.needs_confirmation}. Stored observation: ${stored.observationId || "-"}.`,
      );
    } catch (error) {
      setStatusKey("perception", error.message);
    }
  }

  async function analyzePhoto() {
    if (!photoFile) {
      setStatusKey("perception", "Choose a photo first.");
      return;
    }
    try {
      setStatusKey("perception", "Analyzing photo...");
      const body = new FormData();
      body.append("file", photoFile);
      body.append("mode", "auto");
      body.append("text_hint", textHint);
      const data = await api("/api/v2/vision/analyze", { method: "POST", body });
      const items = data.items || [];
      const stored = await storeObservation("photo", items, {
        fallback: data.fallback,
        notes: data.notes,
        raw_text: data.raw_text,
        image_quality: data.image_quality,
      });
      setObservationSessionId(stored.observationId);
      setCandidates(stored.items);
      setStatusKey(
        "perception",
        `Photo candidates: ${stored.items.length}. needs_confirmation=${data.needs_confirmation}. Stored observation: ${stored.observationId || "-"}.`,
      );
    } catch (error) {
      setStatusKey("perception", error.message);
    }
  }

  async function confirmCandidates() {
    const selected = candidates.filter((candidate) => candidate.selected);
    if (!selected.length) {
      setStatusKey("perception", "No candidates selected.");
      return;
    }

    try {
      if (observationSessionId && selected.every((candidate) => candidate.observation_candidate_id)) {
        const id = householdId || (await loadHousehold());
        await api(`/api/v3/households/${id}/observations/${observationSessionId}/confirm`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            actor: "demo-user",
            reason: "user_confirmed_react_observation_candidates",
            candidates: candidateConfirmations(selected),
          }),
        });
      }
      setPantry((items) => [
        ...items,
        ...selected.map((item) => ({
          name: item.name,
          quantity: Number(item.quantity || 1),
          unit: item.unit || "шт",
          expires_in_days: item.expires_in_days ?? null,
          source: item.source || "vision_candidate",
          confidence: item.confidence ?? null,
        })),
      ]);
      setCandidates([]);
      setObservationSessionId("");
      setStatusKey("perception", "Selected candidates confirmed into pantry.");
    } catch (error) {
      setStatusKey("perception", error.message);
    }
  }

  async function persistPantry() {
    if (!pantry.length) {
      setStatusKey("workspace", "Pantry is empty.");
      return;
    }
    try {
      const id = householdId || (await loadHousehold());
      await api(`/api/v3/households/${id}/pantry/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          actor: "demo-user",
          reason: "user_confirmed_react_pantry",
          items: pantry,
        }),
      });
      setStatusKey("workspace", "Pantry confirmation saved to v3.");
    } catch (error) {
      setStatusKey("workspace", error.message);
    }
  }

  async function interpretContext() {
    try {
      const data = await api("/api/v3/assistant/interpret-context", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: form.contextNote }),
      });
      const proposals = Object.entries(data.proposed_constraints || {})
        .map(([key, value]) => `${key}=${value}`)
        .join(" | ");
      setStatusKey("context", `${proposals}. Evidence: ${(data.evidence || []).join(" ")}`);
    } catch (error) {
      setStatusKey("context", error.message);
    }
  }

  async function generatePlanOptions() {
    try {
      setStatusKey("plan", "Generating explainable draft options...");
      const payload = buildPlanPayload({ pantry, form });
      const data = await api("/api/v3/plans/options", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const options = data.options || [];
      setPlanOptions(options);
      setStatusKey("plan", data.assistant_boundary);
      const balanced = options.find((option) => option.strategy === "balanced") || options[0];
      if (balanced) {
        await refreshCompanion(balanced.plan);
      }
    } catch (error) {
      setStatusKey("plan", error.message);
    }
  }

  async function refreshCompanion(planPayload) {
    try {
      const days = planPayload?.days?.length || 3;
      const data = await api("/api/v3/companion/state", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plan: planPayload,
          pantry,
          protein_goal_g: Number(form.protein || 95),
          budget_per_day: Number(form.budget || 520),
          days,
          mascot: "nerpa",
        }),
      });
      setCompanion(data);
      setStatusKey("companion", data.assistant_boundary);
    } catch (error) {
      setStatusKey("companion", error.message);
    }
  }

  async function approveOption(option) {
    try {
      const id = householdId || (await loadHousehold());
      const event = await api(`/api/v3/households/${id}/plans/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          actor: "demo-user",
          reason: "user_approved_react_plan",
          option,
        }),
      });
      setStatusKey("plan", `Approved: ${event.target_id}`);
      await Promise.all([loadAcceptedPlan(id), loadApprovalEvents(id)]);
    } catch (error) {
      setStatusKey("plan", error.message);
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <h1>Fridge-to-Meal Planner AI</h1>
          <p>Human-controlled food operations copilot. Candidates, drafts and decisions stay reviewable.</p>
        </div>
        <div className="topbar-actions">
          <IconButton icon={RefreshCw} className="secondary" onClick={loadDemo}>
            Demo
          </IconButton>
          <IconButton icon={Database} className="light" onClick={loadHousehold}>
            Household
          </IconButton>
        </div>
      </header>

      <main className="workspace">
        <aside className="control-panel">
          <section>
            <h2>Workspace</h2>
            <label>
              API URL
              <input value={apiBase} onChange={(event) => setApiBase(event.target.value)} />
            </label>
            <div className="status">{status.workspace}</div>
          </section>

          <section>
            <h2>Perception</h2>
            <label>
              Receipt / OCR text
              <textarea value={receiptText} onChange={(event) => setReceiptText(event.target.value)} />
            </label>
            <label>
              Barcodes
              <input value={barcodeText} onChange={(event) => setBarcodeText(event.target.value)} />
            </label>
            <label>
              Text hint
              <input value={textHint} onChange={(event) => setTextHint(event.target.value)} />
            </label>
            <label>
              Product photo
              <input accept="image/*" type="file" onChange={(event) => setPhotoFile(event.target.files?.[0])} />
            </label>
            <div className="toolbar">
              <IconButton icon={ScanLine} onClick={parseReceipt}>
                Parse
              </IconButton>
              <IconButton icon={Camera} className="secondary" onClick={analyzePhoto}>
                Analyze
              </IconButton>
              <IconButton icon={Check} className="light" onClick={confirmCandidates}>
                Confirm
              </IconButton>
            </div>
            <div className="status">{status.perception}</div>
            <CandidateList candidates={candidates} updateCandidate={updateCandidate} />
          </section>

          <section>
            <h2>Confirmed Pantry</h2>
            <PantryEditor pantry={pantry} setPantry={setPantry} updatePantry={updatePantry} />
            <div className="toolbar">
              <IconButton icon={ListChecks} className="light" onClick={() => setPantry([...pantry, emptyPantryItem()])}>
                Add
              </IconButton>
              <IconButton icon={Save} className="secondary" onClick={persistPantry}>
                Save v3
              </IconButton>
              <IconButton icon={X} className="danger" onClick={() => setPantry([])}>
                Clear
              </IconButton>
            </div>
          </section>

          <section>
            <h2>Context and Policy</h2>
            <textarea
              value={form.contextNote}
              onChange={(event) => setForm({ ...form, contextNote: event.target.value })}
            />
            <IconButton icon={Sparkles} className="light full" onClick={interpretContext}>
              Interpret context
            </IconButton>
            <div className="status">{status.context}</div>
            <PolicyForm form={form} setForm={setForm} />
            <IconButton icon={ClipboardCheck} className="full" onClick={generatePlanOptions}>
              Generate draft options
            </IconButton>
          </section>
        </aside>

        <section className="main-panel">
          <div className="metrics">
            <Metric label="Household" value={metrics.household} />
            <Metric label="Pantry" value={metrics.pantry} />
            <Metric label="Draft options" value={metrics.options} />
            <Metric label="Accepted" value={metrics.accepted} />
          </div>

          <section>
            <h2>Companion</h2>
            <CompanionCard companion={companion} status={status.companion} />
          </section>

          <section>
            <h2>Plan Options</h2>
            <div className="status">{status.plan}</div>
            <div className="option-grid">
              {planOptions.length ? (
                planOptions.map((option) => (
                  <PlanOptionCard key={option.option_id} option={option} onApprove={() => approveOption(option)} />
                ))
              ) : (
                <div className="empty">No draft options yet.</div>
              )}
            </div>
          </section>

          <section className="two-column">
            <div>
              <h2>Accepted Plan</h2>
              <AcceptedPlan plan={acceptedPlan} status={status.accepted} />
            </div>
            <div>
              <h2>Approval Events</h2>
              <IconButton icon={RefreshCw} className="light" onClick={() => loadApprovalEvents()}>
                Refresh
              </IconButton>
              <EventList events={events} />
            </div>
          </section>
        </section>
      </main>
    </div>
  );
}

function CandidateList({ candidates, updateCandidate }) {
  if (!candidates.length) return <div className="empty">No candidates yet.</div>;
  return (
    <div className="candidate-list">
      {candidates.map((candidate, index) => (
        <div className="candidate-card" key={`${candidate.name}-${index}`}>
          <input
            checked={Boolean(candidate.selected)}
            type="checkbox"
            onChange={(event) => updateCandidate(index, "selected", event.target.checked)}
          />
          <input value={candidate.name} onChange={(event) => updateCandidate(index, "name", event.target.value)} />
          <input
            min="0"
            step="0.1"
            type="number"
            value={candidate.quantity || 1}
            onChange={(event) => updateCandidate(index, "quantity", Number(event.target.value || 1))}
          />
          <input value={candidate.unit || "шт"} onChange={(event) => updateCandidate(index, "unit", event.target.value)} />
          <span>{Math.round((candidate.confidence || 0) * 100)}%</span>
        </div>
      ))}
    </div>
  );
}

function PantryEditor({ pantry, setPantry, updatePantry }) {
  if (!pantry.length) return <div className="empty">Pantry is empty.</div>;
  return (
    <div className="pantry-list">
      {pantry.map((item, index) => (
        <div className="pantry-row" key={`${item.name}-${index}`}>
          <input value={item.name} onChange={(event) => updatePantry(index, "name", event.target.value)} />
          <input
            min="0"
            step="0.1"
            type="number"
            value={item.quantity}
            onChange={(event) => updatePantry(index, "quantity", Number(event.target.value || 1))}
          />
          <input value={item.unit || "шт"} onChange={(event) => updatePantry(index, "unit", event.target.value)} />
          <input
            placeholder="days"
            type="number"
            value={item.expires_in_days ?? ""}
            onChange={(event) =>
              updatePantry(index, "expires_in_days", event.target.value === "" ? null : Number(event.target.value))
            }
          />
          <button className="icon-only danger" type="button" onClick={() => setPantry(pantry.filter((_, i) => i !== index))}>
            <X size={16} />
          </button>
        </div>
      ))}
    </div>
  );
}

function PolicyForm({ form, setForm }) {
  return (
    <div className="policy-grid">
      <label>
        Budget/day
        <input value={form.budget} type="number" onChange={(event) => setForm({ ...form, budget: event.target.value })} />
      </label>
      <label>
        Calories/day
        <input
          value={form.calories}
          type="number"
          onChange={(event) => setForm({ ...form, calories: event.target.value })}
        />
      </label>
      <label>
        Protein/day
        <input value={form.protein} type="number" onChange={(event) => setForm({ ...form, protein: event.target.value })} />
      </label>
      <label>
        Season
        <select value={form.season} onChange={(event) => setForm({ ...form, season: event.target.value })}>
          <option value="">Any</option>
          <option value="spring">Spring</option>
          <option value="summer">Summer</option>
          <option value="autumn">Autumn</option>
          <option value="winter">Winter</option>
        </select>
      </label>
      <label>
        Allergies
        <input value={form.allergies} onChange={(event) => setForm({ ...form, allergies: event.target.value })} />
      </label>
      <label>
        Disliked
        <input value={form.disliked} onChange={(event) => setForm({ ...form, disliked: event.target.value })} />
      </label>
      <label>
        Max cooking time
        <input
          value={form.maxCookingTime}
          type="number"
          onChange={(event) => setForm({ ...form, maxCookingTime: event.target.value })}
        />
      </label>
      <div className="toggle-row">
        {[
          ["noShopMode", "No shop"],
          ["lowDishes", "Low dishes"],
          ["strictBudget", "Strict budget"],
        ].map(([key, label]) => (
          <label className="toggle" key={key}>
            <input checked={form[key]} type="checkbox" onChange={(event) => setForm({ ...form, [key]: event.target.checked })} />
            {label}
          </label>
        ))}
      </div>
    </div>
  );
}

function CompanionCard({ companion, status }) {
  if (!companion) {
    return <div className="empty">{status}</div>;
  }
  return (
    <div className={`companion-card ${companionTone(companion.state)}`}>
      <div className="mascot">
        <Activity size={24} />
        <b>Nerpa</b>
        <span>{companion.score}%</span>
      </div>
      <div>
        <div className="section-head">
          <h3>
            {companion.display_name}: {companion.state}
          </h3>
          <Pill tone={companionTone(companion.state)}>{companion.visual_hint}</Pill>
        </div>
        <p>{companion.message}</p>
        <div className="signal-row">
          {companion.signals.map((signal) => (
            <Pill key={signal.key} tone={signal.status === "good" ? "good" : "watch"}>
              {signal.label}: {signal.value}
            </Pill>
          ))}
        </div>
        <div className="status">{status}</div>
      </div>
    </div>
  );
}

function PlanOptionCard({ option, onApprove }) {
  const metrics = optionMetrics(option);
  return (
    <article className="option-card">
      <div className="option-head">
        <Pill>{option.strategy}</Pill>
        <h3>{option.title}</h3>
        <p>{option.summary}</p>
        <div className="signal-row">
          {metrics.map((metric) => (
            <Pill key={metric} tone="good">
              {metric}
            </Pill>
          ))}
        </div>
      </div>
      <div className="option-body">
        <IconButton icon={Check} onClick={onApprove}>
          Approve draft
        </IconButton>
        <h4>Decision trace</h4>
        <ul>
          {(option.decision_trace || []).map((item) => (
            <li key={`${option.option_id}-${item.rule}`}>
              <b>{item.rule}</b>: {item.reason}
            </li>
          ))}
        </ul>
        <h4>Meals</h4>
        {(option.plan?.days || []).map((day) => (
          <div className="day" key={`${option.option_id}-${day.day}`}>
            <b>{day.title}</b>
            {Object.values(day.meals || {}).map((meal) => (
              <div className="meal" key={`${day.day}-${meal.label}`}>
                <div className="meal-title">
                  <span>
                    {meal.label}: {meal.recipe?.title}
                  </span>
                  <span>{meal.recipe?.time_min || 0} min</span>
                </div>
                <div className="status">{(meal.reasons || []).join(" | ")}</div>
              </div>
            ))}
          </div>
        ))}
        <h4>Shopping list</h4>
        <ShoppingList items={option.plan?.shopping_list || []} />
      </div>
    </article>
  );
}

function ShoppingList({ items }) {
  if (!items.length) return <div className="empty">No missing ingredients.</div>;
  return (
    <div className="shopping-list">
      {items.map((item, index) => (
        <div className="shopping-item" key={`${item.name}-${index}`}>
          <ShoppingBasket size={16} />
          <div>
            <b>{item.name}</b>
            <p>{item.reason}</p>
          </div>
          <span>
            {item.missing_quantity} {item.unit}
          </span>
        </div>
      ))}
    </div>
  );
}

function AcceptedPlan({ plan, status }) {
  if (!plan) return <div className="empty">{status}</div>;
  const totals = plan.plan_payload?.totals || {};
  return (
    <div className="accepted-card">
      <Pill tone="good">{plan.status}</Pill>
      <h3>{plan.title}</h3>
      <div className="signal-row">
        <Pill>{plan.strategy}</Pill>
        <Pill>{totals.cost || 0} rub</Pill>
        <Pill>{totals.protein_g || 0}g protein</Pill>
      </div>
      <ShoppingList items={plan.shopping_list_payload || []} />
    </div>
  );
}

function EventList({ events }) {
  if (!events.length) return <div className="empty">No approval events yet.</div>;
  return (
    <div className="event-list">
      {events.slice(0, 10).map((event) => (
        <div className="event-card" key={event.id}>
          <div>
            <b>{event.event_type}</b>
            <Pill tone={event.status === "approved" ? "good" : "watch"}>{event.status}</Pill>
          </div>
          <p>{event.reason}</p>
          <span>{event.created_at}</span>
        </div>
      ))}
    </div>
  );
}

export default App;
