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
- Parse receipt/OCR text and demo barcodes into confirmable ingredient candidates.
- Confirm or edit ingredients manually before using them.
- Generate a three-day meal plan and explained shopping list.
- Interpret RU/EN context such as `устал, хочу тёплое без магазина` into visible proposed constraints.
- Compare three planning strategies: simple, waste-first, and balanced.
- Inspect a decision trace for every v3 plan option.
- Approve or override a draft plan from the local demo UI and inspect persisted approval events.
- Review the accepted plan and approve, skip, or change individual shopping-list items.
- Record confirmed purchases and add bought items back into pantry history.
- Generate a household summary report for planned protein, budget usage, pantry usage, shopping load, and purchases.
- Record append-only consent events for photo/receipt retention, analytics, research, and model-training opt-in/out.
- Apply visible policy constraints: allergies, disliked ingredients, no-shop mode, low-dishes mode, max cooking time, and strict budget.
- Show an explainable companion state that reflects plan signals without judging the user or approving decisions.
- Run without an LLM, external API, GPU, or model weights.

## Trust Model

```text
Observation -> Candidate facts -> Human confirmation -> Deterministic planning
            -> Explainable draft options -> Human approval
```

- Vision output is always a candidate and always has `needs_confirmation=true`.
- Observation candidates can be persisted as pending sessions before they become pantry facts.
- V3 plans are always drafts and always have `requires_approval=true`.
- Plan approval and override events are persisted before a draft becomes accepted state.
- Purchase records are explicit user-confirmed events that create confirmed pantry lots.
- Reports are computed from confirmed facts and do not claim what the user actually ate.
- Private data retention, analytics, research, and model-training consent is append-only and revocable.
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

frontend/
├── src/          # React/Vite product demo candidate
└── package.json # frontend scripts and dependency lock
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for boundaries, current limitations, and the target direction.

## Quick Start

Python 3.11-3.13 is recommended for development. The lightweight core also runs on the current local
Python 3.14 environment, but the optional CV stack may not.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -r requirements-dev.txt
python run_local_demo.py
```

`run_local_demo.py` is the safest local demo entrypoint: it uses SQLite even if your private `.env` points to
Docker/PostgreSQL. Use `run_ultra_smart_app.py` only when you intentionally want the normal environment-backed
configuration.

Open:

- Legacy compatibility demo: `http://127.0.0.1:8000/app`
- Swagger: `http://127.0.0.1:8000/docs`
- Readiness: `http://127.0.0.1:8000/health/ready`

React frontend candidate:

```powershell
cd frontend
npm.cmd install --cache .npm-cache
npm.cmd run dev
```

Open `http://127.0.0.1:5173`. The React app talks to the FastAPI backend at `http://127.0.0.1:8000`.

Production React PWA build served by FastAPI:

```powershell
cd frontend
npm.cmd run build
cd ..
python run_local_demo.py
```

Open `http://127.0.0.1:8000/pwa`. The compatibility demo remains available at `/app`.
The production build includes a web app manifest and a conservative service worker that caches the app shell
and static assets, but deliberately avoids caching API, health, and documentation requests.

Docker:

```bash
docker compose up --build
```

Docker Compose starts the FastAPI app on `:8000` and a local PostgreSQL 16 database for v3 pantry/audit
persistence. The app container runs `alembic upgrade head` before starting FastAPI, disables automatic table
creation, builds the React PWA in a Node stage, and serves the compiled app at `/pwa`.

Manual production schema migrations:

```bash
AUTO_CREATE_TABLES=false alembic upgrade head
```

Local Python development keeps `AUTO_CREATE_TABLES=true` by default for fast demos. Docker Compose and
production-like deployments use Alembic migrations with automatic table creation disabled.

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

Parse receipt text and demo barcodes into candidates:

```bash
curl -X POST http://127.0.0.1:8000/api/v2/perception/parse \
  -H "Content-Type: application/json" \
  -d '{"raw_text":"Йогурт 2 шт\nКартофель 3 кг\nЯйца 10 шт","barcodes":["4600000000011"],"source":"receipt"}'
```

Generate a non-authoritative companion state from a draft plan:

```bash
curl -X POST http://127.0.0.1:8000/api/v3/companion/state \
  -H "Content-Type: application/json" \
  -d '{"plan":{"totals":{"protein_g":210,"cost":1200,"budget_limit":1560},"statistics":{"pantry_usage_percent":62},"shopping_list":[]},"protein_goal_g":95,"budget_per_day":520,"days":3,"mascot":"nerpa"}'
```

Record consent for future opt-in training data:

```bash
curl -X POST http://127.0.0.1:8000/api/v3/households/demo-household/consent-events \
  -H "Content-Type: application/json" \
  -d '{"consent_type":"model_training","status":"granted","scope":"photo_feedback_dataset","reason":"opted in after reading privacy notice","policy_version":"privacy-v1"}'
```

Record a confirmed purchase and add it to pantry:

```bash
curl -X POST http://127.0.0.1:8000/api/v3/households/demo-household/purchases \
  -H "Content-Type: application/json" \
  -d '{"source":"shopping_list","items":[{"name":"milk","quantity":2,"unit":"pcs"}],"total_cost":180,"currency":"RUB","reason":"confirmed after shopping"}'
```

Generate a summary report:

```bash
curl "http://127.0.0.1:8000/api/v3/households/demo-household/reports/summary?period_days=3&protein_goal_g=95&budget_per_day=520"
```

## Development Checks

```powershell
.\.venv\Scripts\ruff.exe check app tests migrations run_ultra_smart_app.py run_local_demo.py
.\.venv\Scripts\black.exe --check app tests migrations run_ultra_smart_app.py run_local_demo.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\alembic.exe upgrade head
cd frontend
npm.cmd run test
npm.cmd run build
```

Dependencies are separated by purpose:

- `requirements.txt` - lightweight runtime.
- `requirements-dev.txt` - tests, lint, formatting.
- `requirements-vision.txt` - optional experimental YOLO/OpenCV stack.
- Receipt/barcode parsing uses deterministic heuristics in the core runtime and does not require OCR libraries.

GitHub Actions runs the same backend lint/test checks, frontend test/build checks, Docker contract tests, and
Docker image build.

## Persistence

The app now has a real persistence foundation:

- `GET /api/v3/households/demo` creates a demo household and seeds confirmed pantry lots.
- `GET /api/v3/households/{household_id}/pantry` returns confirmed pantry lots.
- `POST /api/v3/households/{household_id}/pantry/confirm` records user-confirmed pantry items.
- `POST /api/v3/households/{household_id}/observations` stores pending perception candidates.
- `GET /api/v3/households/{household_id}/observations` returns pending and confirmed observation sessions.
- `POST /api/v3/households/{household_id}/observations/{observation_id}/confirm` confirms selected candidates into pantry lots.
- `POST /api/v3/households/{household_id}/plans/approve` records a human-approved plan option.
- `POST /api/v3/households/{household_id}/plans/override` records a human override for a draft plan option.
- `GET /api/v3/households/{household_id}/plans/accepted/latest` returns the latest accepted plan.
- `POST /api/v3/households/{household_id}/shopping-list/decide` records item-level shopping decisions.
- `POST /api/v3/households/{household_id}/purchases` records confirmed purchases and creates pantry lots.
- `GET /api/v3/households/{household_id}/purchases` returns purchase history.
- `GET /api/v3/households/{household_id}/reports/summary` returns planned nutrition, budget, pantry, shopping, and purchase metrics.
- `GET /api/v3/households/{household_id}/approval-events` returns append-only plan decision events.
- `POST /api/v3/households/{household_id}/consent-events` records append-only consent decisions.
- `GET /api/v3/households/{household_id}/consent-events` returns consent history.
- `GET /api/v3/households/{household_id}/consents/current` returns the latest consent state by type and scope.
- `GET /api/v3/households/{household_id}/audit-events` returns append-only audit events.

Local Python uses SQLite by default. Docker Compose uses PostgreSQL. Both paths use the same async
SQLAlchemy models and v3 API. Alembic migrations live in `migrations/`; the first migration creates the
current v3 persistence schema.

## Current Limitations

- The static frontend demonstrates the v3 flow and is retained as a compatibility demo at `/app`.
- The React/Vite frontend in `frontend/` is the target PWA direction and can be served by FastAPI at `/pwa` after `npm run build`.
- The PWA shell includes `manifest.webmanifest`, a maskable SVG icon, and a service worker for offline app-shell caching.
- Companion state is a deterministic UX layer, not a medical, body-image, or autonomous decision system.
- The Docker image builds and serves the React PWA, while local Python can run with or without `frontend/dist`.
- Offline support is limited to the app shell and static assets; mutable API data is always fetched live.
- The bundled recipe catalog contains 50 demo recipes and approximate nutrition/cost values.
- Photo analysis is a safe color/text fallback, not reliable ingredient recognition.
- Receipt/barcode parsing is demo-grade and still requires user confirmation.
- Docker Compose is wired to run Alembic migrations before FastAPI startup.
- Production migrations are available through Alembic, but there is not yet a full backup/restore runbook.
- Consent events are tracked, but there is not yet a full privacy settings UI.
- Purchase events close the shopping loop, but there is not yet receipt reconciliation or spend analytics.
- Reports summarize confirmed plans and purchases, but there are no consumption events yet.

## Roadmap

1. Finish replacing the static frontend with the bilingual React PWA, offline-safe local state management, and richer UX polish.
2. Add policy YAML, richer hard constraints, and OR-Tools optimization.
3. Evolve the companion into a tasteful mascot layer with opt-in visual states, accessibility, and no body-shaming.
4. Add real OCR integration and barcode databases before training custom computer vision.
5. Build opt-in feedback datasets, ranking, and waste-risk models on top of explicit consent events.
6. Add authentication, household isolation, and a full deployment runbook.

## Security

Never commit `.env`, `.venv`, cache files, local databases, model weights, uploaded photos, or receipts.
Use `.env.example` for public configuration. Raw user images must be treated as private and should be deleted
after processing unless the user explicitly opts into retention.
Consent events are append-only: revoking consent creates a new event instead of deleting history.

## License

MIT

Created by artemxdata
