"""Helpers for publishing Cognosphere frameworks into AgenticTrade."""
from __future__ import annotations

from typing import Any

from marketplace.registry import ServiceRegistry

from .catalog import COGNOSPHERE_V1


def publish_framework(
    registry: ServiceRegistry,
    *,
    provider_id: str,
    base_url: str,
    framework_id: str = "cognosphere.business.intelligence.v1",
) -> Any:
    """Publish one Cognosphere framework as a normal AgenticTrade service."""
    framework = next(
        (item for item in COGNOSPHERE_V1 if item.framework_id == framework_id),
        None,
    )
    if framework is None:
        raise ValueError(f"framework_not_found:{framework_id}")

    endpoint = f"{base_url.rstrip('/')}/api/v1/cognosphere/frameworks/{framework.framework_id}"
    return registry.register(
        provider_id=provider_id,
        name=framework.name,
        description=framework.purpose,
        endpoint=endpoint,
        price_per_call=framework.price_usdc,
        category=framework.domain,
        tags=list(framework.capability_tags),
        payment_method="nowpayments",
        free_tier_calls=0,
        metadata={
            "capability_id": framework.framework_id,
            "capability_version": framework.version,
            "artifact_type": "cognosphere_framework",
            "risk_class": framework.risk_class,
            "delivery": "public_framework_package",
        },
    )
