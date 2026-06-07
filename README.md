# Fridge-to-Meal Planner AI

[![CI](https://github.com/artemxdata/Fridge-to-Meal-Planner-AI/actions/workflows/ci.yml/badge.svg)](https://github.com/artemxdata/Fridge-to-Meal-Planner-AI/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![Human controlled](https://img.shields.io/badge/AI-human--controlled-147a5c.svg)](#trust-model)

Human-controlled food operations copilot for people who do not want to spend mental energy deciding what
to cook or buy.

The system observes possible pantry items, asks the user to confirm facts, and produces several explainable
meal-plan drafts. AI can suggest and explain; it cannot silently change the pantry, approve a plan, or create
a final shopping list.

## Current Product Increment

- Upload a fridge/product photo and receive low-confidence ingredient candidates.
- Confirm or edit ingredients manually before using them.
- Generate a three-day meal plan and explained shopping list.
- Interpret RU/EN context such as `устал, хочу тёплое без магазина` into visible proposed constraints.
- Compare three planning strategies: simple, waste-first, and balanced.
- Inspect a decision trace for every v3 plan option.
- Approve or override a draft plan from the local demo UI and inspect persisted approval events.
- Review the accepted plan and approve, skip, or change individual shopping-list items.
- Apply visible policy constraints: allergies, disliked ingredients, no-shop mode, low-dishes mode, max cooking time, and strict budget.
- Run without an LLM, external API, GPU, or model weights.

## Trust Model

```text
Observation -> Candidate facts -> Human confirmation -> Deterministic planning
            -> Explainable draft options -> Human approval
```

- Vision output is always a candidate and always has `needs_confirmation=true`.
- V3 plans are always drafts and always have `requires_approval=true`.
- Plan approval and override events are persisted before a draft becomes accepted state.
- Context interpretation proposes structured constraints but requires confirmation.
- Existing `/api/v2/*` contracts remain available while the product evolves through `/api/v3/*`.

## Architecture

```text
app/
├── api/          # FastAPI transport layer and versioned routes
├── services/     # deterministic planning, vision fallback, context interpretation
├── catalog.py    # recipe catalog and ingredient normalization
├── config.py     # environment-backed safe defaults
├── schemas.py    # public request/response contracts
└── main.py       # application factory, health checks, middleware
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for boundaries, current limitations, and the target direction.

## Quick Start

Python 3.11-3.13 is recommended for development. The lightweight core also runs on the current local
Python 3.14 environment, but the optional CV stack may not.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python run_ultra_smart_app.py
```

Open:

- Product demo: `http://127.0.0.1:8000/app`
- Swagger: `http://127.0.0.1:8000/docs`
- Readiness: `http://127.0.0.1:8000/health/ready`

Docker:

```bash
docker compose up --build
```

Docker Compose starts the FastAPI app on `:8000` and a local PostgreSQL 16 database for v3 pantry/audit
persistence.

## API Examples

Interpret human context without applying it:

```bash
curl -X POST http://127.0.0.1:8000/api/v3/assistant/interpret-context \
  -H "Content-Type: application/json" \
  -d '{"text":"Я устал, хочу тёплое без магазина"}'
```

Generate three explainable draft options:

```bash
curl -X POST http://127.0.0.1:8000/api/v3/plans/options \
  -H "Content-Type: application/json" \
  -d '{"pantry":[{"name":"яйца","quantity":6},{"name":"картофель","quantity":4}],"budget_per_day":520}'
```

Generate options with explicit policy constraints:

```bash
curl -X POST http://127.0.0.1:8000/api/v3/plans/options \
  -H "Content-Type: application/json" \
  -d '{"pantry":[{"name":"овсянка","quantity":2},{"name":"йогурт","quantity":2}],"budget_per_day":520,"days":1,"policy":{"allergies":["яйца"],"max_cooking_time_min":25,"low_dishes":true}}'
```

## Development Checks

```powershell
.\.venv\Scripts\ruff.exe check app tests run_ultra_smart_app.py
.\.venv\Scripts\black.exe --check app tests run_ultra_smart_app.py
.\.venv\Scripts\python.exe -m pytest -q
```

Dependencies are separated by purpose:

- `requirements.txt` - lightweight runtime.
- `requirements-dev.txt` - tests, lint, formatting.
- `requirements-vision.txt` - optional experimental YOLO/OpenCV stack.

## Persistence

The app now has a real persistence foundation:

- `GET /api/v3/households/demo` creates a demo household and seeds confirmed pantry lots.
- `GET /api/v3/households/{household_id}/pantry` returns confirmed pantry lots.
- `POST /api/v3/households/{household_id}/pantry/confirm` records user-confirmed pantry items.
- `POST /api/v3/households/{household_id}/plans/approve` records a human-approved plan option.
- `POST /api/v3/households/{household_id}/plans/override` records a human override for a draft plan option.
- `GET /api/v3/households/{household_id}/plans/accepted/latest` returns the latest accepted plan.
- `POST /api/v3/households/{household_id}/shopping-list/decide` records item-level shopping decisions.
- `GET /api/v3/households/{household_id}/approval-events` returns append-only plan decision events.
- `GET /api/v3/households/{household_id}/audit-events` returns append-only audit events.

Local Python uses SQLite by default. Docker Compose uses PostgreSQL. Both paths use the same async
SQLAlchemy models and v3 API.

## Current Limitations

- The static frontend now demonstrates v3 option comparison, policy constraints, accepted plan state, and shopping-list item decisions.
- The frontend is still a single static file, not a React PWA.
- The bundled recipe catalog contains 50 demo recipes and approximate nutrition/cost values.
- Photo analysis is a safe color/text fallback, not reliable ingredient recognition.
- Docker Compose is verified locally with the FastAPI app and PostgreSQL service.

## Roadmap

1. Replace the static frontend with a bilingual React PWA and richer state management.
2. Add policy YAML, richer hard constraints, and OR-Tools optimization.
3. Add barcode and receipt OCR before training custom computer vision.
4. Build opt-in feedback datasets, ranking, and waste-risk models.
5. Add authentication, household isolation, and production migrations.

## Security

Never commit `.env`, `.venv`, cache files, local databases, model weights, uploaded photos, or receipts.
Use `.env.example` for public configuration. Raw user images must be treated as private and should be deleted
after processing unless the user explicitly opts into retention.

## License

MIT
