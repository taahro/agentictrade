"""Runtime packaging for public Cognosphere framework deliveries.

This module turns catalog entries into deterministic, versioned capability
packages. It exposes only the public abstraction layer; private Void
architecture and unpublished implementation details are intentionally absent.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .catalog import COGNOSPHERE_V1, FrameworkCard


def get_framework(framework_id: str) -> FrameworkCard:
    for framework in COGNOSPHERE_V1:
        if framework.framework_id == framework_id:
            return framework
    raise KeyError(f"framework_not_found:{framework_id}")


def build_framework_package(
    framework_id: str,
    *,
    buyer_id: str = "",
    requested_inputs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the deterministic public artifact delivered to a buyer agent."""
    framework = get_framework(framework_id)
    framework.validate()

    payload = {
        "artifact_type": "cognosphere_framework",
        "framework": {
            "framework_id": framework.framework_id,
            "name": framework.name,
            "version": framework.version,
            "domain": framework.domain,
            "purpose": framework.purpose,
            "stages": list(framework.stages),
            "inputs": list(framework.inputs),
            "outputs": list(framework.outputs),
            "capability_tags": list(framework.capability_tags),
            "price_usdc": str(framework.price_usdc),
            "risk_class": framework.risk_class,
        },
        "delivery_contract": {
            "buyer_id": buyer_id,
            "delivery_type": "public_framework_package",
            "usage": "Use the framework stages, input contract, output contract, and decision workflow as an abstract capability.",
            "execution_boundary": "The package contains public abstractions only; private Void architecture, proprietary mappings, and unpublished mechanisms are excluded.",
        },
        "request": dict(requested_inputs or {}),
    }

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload["artifact_id"] = "cgp_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]
    payload["integrity"] = {
        "algorithm": "sha256",
        "canonical_payload": "artifact payload before integrity field",
    }
    return payload


def verify_framework_package(package: Mapping[str, Any]) -> bool:
    """Verify the package has the minimum structure expected for delivery."""
    required = {"artifact_type", "framework", "delivery_contract", "artifact_id", "integrity"}
    if not required.issubset(package):
        return False
    framework = package.get("framework")
    if not isinstance(framework, Mapping):
        return False
    return all(
        bool(framework.get(key))
        for key in ("framework_id", "name", "version", "inputs", "outputs", "stages")
    )
