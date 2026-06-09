# Architecture

## Product Principle

Fridge-to-Meal Planner AI is a human-controlled decision-support system. Models may observe, rank, translate,
or explain. They do not own facts or approve changes.

The main invariant is:

> No observation, interpreted context, plan, or shopping list becomes accepted state without an explicit
> human approval event.

## Current Runtime

The current increment is a modular FastAPI monolith:

```text
HTTP request
  -> versioned API router
  -> validated Pydantic schema
  -> deterministic application service
  -> response with explicit confirmation/approval boundary
```

Responsibilities:

- `api`: HTTP parsing, status codes, compatibility contracts.
- `services`: deterministic planning and candidate generation.
- `catalog`: recipe loading and ingredient name normalization.
- `schemas`: public contracts and validation.
- `config`: environment-backed safe defaults and filesystem paths.

The legacy `run_ultra_smart_app.py` remains a compatibility entrypoint only.
The static `index.html` is a compatibility demo surface for the v3 human-control workflow and remains
available at `/app`. The target frontend direction lives in `frontend/` as a React/Vite PWA candidate with
componentized state for perception, observation confirmation, planning, companion feedback, accepted plans,
and approval events. When `frontend/dist` exists, FastAPI serves the compiled React build at `/pwa`; the
Docker image builds that frontend in a dedicated Node stage. The React build includes a manifest, SVG icon,
and a conservative service worker that caches only the app shell and static assets; API requests are always
live to avoid stale pantry, approval, and shopping decisions.

## API Versions

- `/api/v2`: stable MVP compatibility routes used by the existing static demo.
- `/api/v3`: human-controlled product contracts. Responses are drafts and include an approval boundary.

V3 currently supports transparent context interpretation, explainable plan options, and durable plan
approval/override events backed by persistence and audit history.
Household-scoped routes use a shared dependency to reject unknown households before domain operations run.
Privacy-sensitive retention and training permissions are tracked as append-only consent events.

## Decision Flow

```text
Confirmed pantry + explicit preferences + proposed context
    -> deterministic recipe scoring
    -> simple / waste-first / balanced draft plans
    -> decision trace and trade-offs
    -> ApprovalEvent after explicit approval or override
    -> item-level shopping decisions
    -> PurchaseEvent after explicit purchase confirmation
```

The current scoring engine is a deterministic baseline. OR-Tools CP-SAT will replace it when recipe units,
hard constraints, and pantry lots are modeled precisely.
V3 plan options already apply visible policy constraints before ranking: allergies, disliked ingredients,
no-shop mode, low-dishes preference, max cooking time, and strict budget. Applied constraints are included in
the decision trace.

## Companion State

The companion is a deterministic UX layer over already visible plan signals. It can summarize protein target
fit, budget fit, pantry usage, use-soon items, and shopping load. It must not infer body shape, shame the user,
approve plans, change pantry facts, or make autonomous health decisions.

The current mascot direction is a neutral nerpa-style companion. Its state reflects system workload and plan
trade-offs, not the user's body.

## Perception Flow

```text
Photo / receipt / barcode
    -> candidate observations with source and confidence
    -> pending observation session
    -> confidence policy
    -> user confirmation
    -> pantry lot
```

The current Pillow color/text heuristic is deliberately labeled as fallback. Generic YOLO code remains
experimental and is not imported by the runtime.
Receipt text and demo barcodes are parsed by deterministic heuristics in the core runtime. This gives the
project a practical perception path before expensive OCR/CV work, while preserving manual confirmation.
V3 observation sessions persist candidates as pending records, so the gap between perception and confirmed
pantry facts is auditable.

Photo, receipt, analytics, research, and model-training permissions are modeled separately from perception
itself. A user can grant, deny, or revoke consent, and the current consent state is derived from the latest
append-only event per `consent_type + scope`.

## Persistence

The current persistence increment uses async SQLAlchemy with SQLite fallback and PostgreSQL in Docker Compose.
Alembic migrations under `migrations/` are the production schema path; local development can still use
`AUTO_CREATE_TABLES=true` for quick demos. Docker Compose runs migrations before app startup and sets
`AUTO_CREATE_TABLES=false`.

Implemented now:

- demo household;
- confirmed pantry lots;
- pending and confirmed observation sessions;
- latest accepted plan state after explicit plan approval;
- deterministic policy constraints for v3 plan options;
- deterministic companion state for explainable plan feedback;
- append-only approval events for plan approval and override;
- append-only approval events for item-level shopping decisions;
- purchase events that add user-confirmed shopping results back into pantry lots;
- append-only consent events for private data retention, analytics, research, and model-training opt-in/out;
- append-only audit events for household creation, pantry confirmation, plan decisions, and shopping decisions;
- Alembic migrations for the current persistence schema.
- centralized household existence checks for v3 household-scoped routes.

Still planned:

- households and users;

All records must be scoped by `household_id`. Cross-household access tests are mandatory before exposing
authentication.

## Safety and Operations

- CORS defaults to local known origins rather than `*`.
- Upload reads are bounded and image pixel count is limited.
- Requests receive an `X-Request-ID`.
- Health endpoints separate liveness from readiness.
- Optional CV dependencies are excluded from the core runtime.
- The Docker entrypoint can run Alembic migrations before serving traffic.
- External LLM/VLM integrations must use timeouts, structured outputs, model versions, and graceful fallback.

## Known Gaps

- No full deployment runbook for migration ordering, rollback, and backup/restore yet.
- No authentication yet; household isolation is currently path-scoped and tested, but not identity-backed.
- No policy YAML or OR-Tools constraint solver yet.
- React PWA offline-safe local state management and final deploy routing are not finished yet.
- No calibrated CV/OCR models, production barcode database, or evaluation dataset.
- No final mascot asset system or animation pipeline yet.
