# Fridge-to-Meal Planner AI

AI-assisted meal planner that turns a home pantry into a practical weekly meal plan.

The project is being rebuilt from a prototype into a GitHub portfolio MVP: upload or enter available products, confirm the pantry, set budget and nutrition goals, generate meal ideas, and get a shopping list for missing ingredients.

## Current Status

This repository currently contains a working prototype:

- FastAPI backend with recipe suggestion and daily meal planning.
- Static HTML frontend for manual pantry input.
- Russian recipe dataset with calories, protein, carbs, fats, season tags, cooking time, and estimated cost.
- Simple photo analysis endpoint based on Pillow and fallback heuristics.

The computer vision module is not the core MVP yet. The reliable flow is manual pantry input plus user confirmation. Vision should be treated as an optional demo/assistant feature.

## Features

- Suggest a recipe from available pantry items.
- Build a daily meal plan by budget, season and nutrition goals.
- Calculate total calories, protein, carbs, fats and estimated cost.
- Show missing ingredients for shopping.
- Store pantry state in browser `localStorage`.
- Photo upload flow with simple color/text fallback and manual confirmation.

## Tech Stack

- Python
- FastAPI
- Pydantic
- Uvicorn
- HTML/CSS/JavaScript
- Pillow-based image fallback for the MVP
- Pytest for future tests

## Quick Start

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Run the API:

```powershell
python run_ultra_smart_app.py
```

Open API docs:

```text
http://127.0.0.1:8000/docs
```

Open `index.html` in a browser and keep the API base URL as:

```text
http://127.0.0.1:8000
```

## API Endpoints

Current endpoints:

- `GET /` - health/status response.
- `GET /api/v2/recipes/sample` - sample recipes.
- `POST /api/v2/suggest` - suggest one recipe.
- `POST /api/v2/plan` - build a daily meal plan.

Planned MVP endpoints:

- `POST /api/v2/weekly-plan`
- `POST /api/v2/shopping-list`
- `POST /api/v2/statistics/summary`
- `POST /api/v2/vision/analyze`

## Computer Vision Notes

The current MVP uses a lightweight fallback approach instead of requiring expensive or heavy computer vision dependencies.

For the MVP, the expected flow is:

1. User enters products manually or uploads a photo in demo/experimental mode.
2. The system proposes detected ingredients with confidence.
3. User confirms or edits the list.
4. Only confirmed products are used for planning.

This avoids pretending that generic computer vision can reliably identify products like cottage cheese, kefir, flour, buckwheat or exact packaged goods without a trained dataset or paid vision API.

## Security

Do not commit local secrets.

Ignored local files include:

- `.env`
- `.venv/`
- model weights like `*.pt`
- cache and build artifacts

Use `.env.example` for public configuration examples when it is added.

## Roadmap

- Refactor backend into `app/` package.
- Add weekly meal planning.
- Add structured shopping list with categories and estimated cost.
- Add nutrition and budget dashboard.
- Improve upload/demo vision endpoint with user confirmation.
- Add tests and CI.
- Fix Docker entrypoint and add `.dockerignore`.
- Add PostgreSQL, Redis and Alembic only after persistent user data is implemented.
- Add optional OCR for receipts and labels.
- Add Telegram or n8n integration for portfolio extensions.
