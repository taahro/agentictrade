# Cognosphere Provider Runtime

This layer turns the public Cognosphere catalog into a deliverable agent
capability without exposing private Void architecture.

## What a buyer receives

A successful purchase of a Cognosphere framework returns a deterministic
cognosphere_framework artifact containing:

- framework identity and semantic version
- purpose and domain
- ordered stages
- input contract
- output contract
- capability tags
- price/risk metadata
- buyer-bound delivery contract
- artifact identifier

The package is a public intellectual-framework product, not a dump of private
research or proprietary implementation mechanisms.

## Agent flow

Discover catalog
    ↓
Inspect Business Intelligence v1
    ↓
Request through AgenticTrade service
    ↓
Payment rail authorizes transaction
    ↓
Cognosphere provider delivers package
    ↓
Buyer verifies artifact structure/version
    ↓
Outcome + reputation + settlement

## Provider registration

The runtime exposes the delivery endpoint:

GET /api/v1/cognosphere/frameworks/{framework_id}

The existing AgenticTrade service registry and payment proxy remain the
economic entry point. No duplicate marketplace or payment system is introduced.

## First-sale target

The first commercial transaction remains:

Buyer Agent → Cognosphere Business Intelligence v1 → 10 USDC → verified delivery

No live payment or secret is required for this code path. Live activation should
be performed only after the service is registered with the real provider ID and
the buyer/provider credentials are configured.
