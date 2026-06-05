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

## API Versions

- `/api/v2`: stable MVP compatibility routes used by the existing static demo.
- `/api/v3`: human-controlled product contracts. Responses are drafts and include an approval boundary.

V3 currently supports transparent context interpretation and explainable plan options. It intentionally does
not expose a fake approval endpoint before persistence and audit history exist.

## Decision Flow

```text
Confirmed pantry + explicit preferences + proposed context
    -> deterministic recipe scoring
    -> simple / waste-first / balanced draft plans
    -> decision trace and trade-offs
    -> future ApprovalEvent
```

The current scoring engine is a deterministic baseline. OR-Tools CP-SAT will replace it when recipe units,
hard constraints, and pantry lots are modeled precisely.

## Perception Flow

```text
Photo / receipt / barcode
    -> candidate observations with source and confidence
    -> confidence policy
    -> user confirmation
    -> pantry lot
```

The current Pillow color/text heuristic is deliberately labeled as fallback. Generic YOLO code remains
experimental and is not imported by the runtime.

## Persistence

The current persistence increment uses async SQLAlchemy with SQLite fallback and PostgreSQL in Docker Compose.

Implemented now:

- demo household;
- confirmed pantry lots;
- append-only audit events for household creation and pantry confirmation.

Still planned:

- households and users;
- purchase events;
- observation sessions and candidates;
- plans and shopping lists;
- append-only approval, override, consent, and audit events.

All records must be scoped by `household_id`. Cross-household access tests are mandatory before exposing
authentication.

## Safety and Operations

- CORS defaults to local known origins rather than `*`.
- Upload reads are bounded and image pixel count is limited.
- Requests receive an `X-Request-ID`.
- Health endpoints separate liveness from readiness.
- Optional CV dependencies are excluded from the core runtime.
- External LLM/VLM integrations must use timeouts, structured outputs, model versions, and graceful fallback.

## Known Gaps

- No durable plan approval or override workflow yet.
- No authentication or household isolation yet.
- No policy YAML or hard allergy constraints yet.
- No React PWA.
- No calibrated CV/OCR models or evaluation dataset.
