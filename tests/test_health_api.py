from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

pytestmark = pytest.mark.anyio


async def test_liveness_requires_no_identity_headers(client: httpx.AsyncClient) -> None:
    """AC-1.1, AC-1.4: liveness is public and returns exactly the alive payload."""
    response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}
    assert "error" not in response.json()


async def test_readiness_succeeds_when_services_are_initialized(
    client: httpx.AsyncClient,
) -> None:
    """AC-1.2, AC-1.4: readiness reports composition without tenant data or auth."""
    response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    assert "store_id" not in response.json()
    assert "error" not in response.json()


async def test_readiness_not_ready_does_not_affect_liveness(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    """AC-1.3: a missing required service yields 503 while liveness remains 200."""
    delattr(app.state, "alert_service")

    ready_response = await client.get("/health/ready")
    live_response = await client.get("/health/live")

    assert ready_response.status_code == 503
    assert ready_response.json() == {"status": "not_ready"}
    assert live_response.status_code == 200
    assert live_response.json() == {"status": "alive"}


async def test_health_routes_are_documented_without_security(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    """AC-1.1, AC-1.2, AC-1.4: both public probes appear in OpenAPI."""
    live_response = await client.get("/health/live")
    ready_response = await client.get("/health/ready")
    openapi = app.openapi()
    paths = openapi["paths"]

    assert live_response.status_code == 200
    assert ready_response.status_code == 200
    assert "/health/live" in paths
    assert "/health/ready" in paths
    assert "security" not in paths["/health/live"]["get"]
    assert "security" not in paths["/health/ready"]["get"]
