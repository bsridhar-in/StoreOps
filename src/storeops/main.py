"""ASGI entrypoint: ``uvicorn storeops.main:app --reload``."""

from storeops.app import create_app

app = create_app()
