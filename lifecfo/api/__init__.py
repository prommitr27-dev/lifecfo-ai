"""HTTP API for the mobile app. Run: `uv run uvicorn lifecfo.api.main:app`."""

from lifecfo.api.app import create_app

__all__ = ["create_app"]
