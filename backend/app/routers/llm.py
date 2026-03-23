"""LLM status check endpoint."""

from __future__ import annotations

import httpx
from fastapi import APIRouter

from app.config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL

router = APIRouter()


@router.get("/api/llm/status")
async def llm_status():
    """Check if the LLM backend is reachable and return model info."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{OPENAI_BASE_URL}/models",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            )
            resp.raise_for_status()
            data = resp.json()

            # Try to find the configured model in the response
            model_name = OPENAI_MODEL
            if isinstance(data, dict) and "data" in data:
                for m in data["data"]:
                    if m.get("id") == OPENAI_MODEL:
                        model_name = m["id"]
                        break

            return {"status": "online", "model": model_name}
    except Exception:
        return {"status": "offline", "model": None}
