"""ASGI entry point: `uv run uvicorn lifecfo.api.main:app --host 0.0.0.0 --port 8000`."""

from lifecfo.api.app import create_app

app = create_app()
