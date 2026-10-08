"""Public Cognosphere capability delivery routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from cognosphere.catalog import COGNOSPHERE_V1
from cognosphere.runtime import build_framework_package

router = APIRouter(prefix="/cognosphere", tags=["cognosphere"])


@router.get("/catalog")
async def cognosphere_catalog():
    """Return the public framework catalog for agent discovery."""
    return {
        "catalog_version": "1.0.0",
        "frameworks": [
            {
                "framework_id": item.framework_id,
                "name": item.name,
                "version": item.version,
                "domain": item.domain,
                "purpose": item.purpose,
                "stages": list(item.stages),
                "inputs": list(item.inputs),
                "outputs": list(item.outputs),
                "capability_tags": list(item.capability_tags),
                "price_usdc": str(item.price_usdc),
                "risk_class": item.risk_class,
            }
            for item in COGNOSPHERE_V1
        ],
    }


@router.get("/frameworks/{framework_id}")
async def deliver_framework(
    framework_id: str,
    buyer_id: str = Query(default=""),
):
    """Deliver one public Cognosphere framework package.

    Payment is intentionally handled by AgenticTrade's existing proxy/payment
    rails before a buyer reaches this provider endpoint.
    """
    try:
        return build_framework_package(framework_id, buyer_id=buyer_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
