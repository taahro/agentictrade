# Phase 3 — Provider Capability Economy

Phase 3 gives the provider side a machine-readable contract that can be consumed by autonomous buyers.

## Provider runtime contract

\`\`\`
Capability Card
    ↓
Request arrives
    ↓
Provider Policy Check
    ↓
Quote generated
    ↓
Buyer accepts
    ↓
Delivery Contract
    ↓
Execute capability
    ↓
Return result
    ↓
Receipt / reputation / settlement
\`\`\`

## Capability Card

\`CapabilityCard\` describes:

- provider and service identity
- capability identity and version
- description, category and tags
- input and output schemas
- price and currency
- supported delivery modes
- SLA guarantees
- provider terms
- active/inactive state

Cards expose \`as_dict()\` so they can become a public machine-readable discovery/negotiation format.

## Provider Quote Policy

\`ProviderQuotePolicy\` performs deterministic checks before generating an offer:

- capability is active
- buyer/provider and service identity match
- currency is compatible
- buyer maximum price is respected
- provider's own price ceiling is respected
- requested delivery mode is supported
- quote TTL is valid

\`generate_offer()\` returns the existing \`CapabilityOffer\` contract used by Phase 2.

Until the provider network endpoint is added, the quote engine is transport-neutral. This keeps the capability contract reusable for REST, MCP, or other agent transports.

## Delivery Contract

\`CapabilityDeliveryContract\` is created after an offer is accepted. It freezes the agreed:

- buyer
- provider
- service
- capability/version
- price/currency
- delivery mode
- output schema
- SLA
- terms
- delivery deadline, when supplied

This separates **what was advertised**, **what was offered**, and **what was accepted**.

## Example

\`\`\`python
from decimal import Decimal

from marketplace.agent_economy import CapabilityNeed, CapabilityCandidate, create_request, accept_offer
from marketplace.provider_economy import (
    CapabilityCard,
    CapabilityDeliveryContract,
    ProviderQuotePolicy,
)

card = CapabilityCard(
    capability_id="cap-risk-analysis-v1",
    provider_id="risk-agent",
    service_id="risk-service",
    name="Risk Analysis",
    category="finance",
    tags=("risk", "portfolio"),
    input_schema={"type": "object"},
    output_schema={"type": "object"},
    price=Decimal("0.005"),
    currency="USDC",
    delivery_modes=("sync", "async"),
    sla={"max_latency_ms": 2000, "min_uptime_pct": 99.0},
)

request = create_request(
    buyer_id="trading-agent",
    candidate=CapabilityCandidate(
        service_id=card.service_id,
        provider_id=card.provider_id,
        name=card.name,
        price=float(card.price),
        currency=card.currency,
    ),
    need=CapabilityNeed(
        name=card.name,
        category=card.category,
        tags=card.tags,
        max_price=0.01,
        currency="USDC",
    ),
)

policy = ProviderQuotePolicy(quote_ttl_seconds=300)
offer = policy.generate_offer(request, card)
receipt = accept_offer(request, offer)
contract = CapabilityDeliveryContract.from_acceptance(
    request, offer, card, receipt
)
\`\`\`

## Current boundary

Phase 3 currently implements the **provider contract layer**. The next increment is runtime exposure through the Provider Agent and/or a dedicated capability endpoint so remote agents can retrieve cards and request quotes directly.

Phase 2's first funded Base Sepolia smoke test remains a validation checkpoint; it does not require a main-branch merge.
