"""Backward-compatible entrypoint for the Fridge-to-Meal Planner MVP."""

import uvicorn

from app.main import app

__all__ = ["app"]


if __name__ == "__main__":
    print("Fridge-to-Meal Planner AI: http://127.0.0.1:8000/app")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
