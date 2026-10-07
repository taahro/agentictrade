# Phase 5 — Agent Economy

Phase 5 is the final planned layer in the current AgenticTrade capability-economy roadmap.

It does not create another marketplace. It turns capability activity into reusable economic behavior.

## Economic loop

\`\`\`
Capability
   ↓
Utility
   ↓
Outcome
   ↓
Reputation
   ↓
Better selection + pricing
   ↓
Revenue
   ↓
More capability
   ↓
Composite capability
   ↓
New market value
\`\`\`

## Outcome-based reputation

\`CapabilityOutcome\` records the observable result of a capability delivery:

- success
- quality score
- verified value score
- latency
- price/currency
- buyer and provider
- capability identity

\`OutcomeReputationPolicy\` converts those observations into a deterministic 0–10 outcome score. Verification is deliberately stronger than an unverified value claim.

This layer complements the existing usage-based \`ReputationEngine\`; it does not overwrite historical platform reputation.

## Dynamic pricing

\`DynamicPricingPolicy\` lets providers vary price from explicit economic signals:

- utilization
- current reputation
- demand

The policy is bounded by minimum/maximum price and a minimum/maximum multiplier. This makes pricing machine-readable and deterministic rather than an uncontrolled model decision.

Example:

\`\`\`python
policy = DynamicPricingPolicy(
    base_price=Decimal("0.01"),
    min_price=Decimal("0.006"),
    max_price=Decimal("0.015"),
)

quote = policy.quote(
    utilization=8,
    reputation=9,
    demand=7,
)
\`\`\`

## Agent-to-agent referrals

\`ReferralPolicy\` allows a capability transaction to attribute a bounded reward to another agent that referred the buyer.

The Phase 5 accounting rule is explicit:

\`\`\`
purchase
  ├── buyer debit
  ├── provider revenue
  ├── optional platform fee
  └── optional referral reward
\`\`\`

Referral rewards are taken from the provider-side economic allocation; they cannot create value outside the transaction amount.

## Composite capabilities and resale

\`CompositeCapability\` represents a higher-level capability built from other capabilities.

For example:

\`\`\`
Market Data Agent
       +
Research Agent
       +
Risk Agent
       ↓
Decision Agent
       ↓
"Risk-Aware Trading Decision"
\`\`\`

The composite records its component capability IDs and provenance. That means a downstream buyer can see that a result is composed rather than treating it as an opaque primitive.

This creates the economic possibility of specialization and resale:

**buy narrow capability → combine → create higher-value capability → sell outcome.**

## Cross-agent accounting

\`EconomyLedger\` provides a deterministic accounting projection for agent-to-agent activity.

It can record:

- capability purchase debit
- provider revenue credit
- platform fee attribution
- referral reward attribution
- transaction/reference IDs
- per-agent balance projections

The ledger is intentionally **not** a payment rail. It does not custody funds, sign transactions, or settle on-chain assets. Existing x402, escrow, and settlement infrastructure remains authoritative for actual money movement.

## Phase 5 boundary

The current implementation establishes the economic primitives without prematurely coupling them to database schema or live settlement internals.

That keeps the next step open for runtime integration:

\`\`\`
Chain Result
    ↓
Outcome Observation
    ↓
Outcome Reputation
    ↓
Provider Pricing
    ↓
Referral / Attribution
    ↓
Composite Capability
    ↓
Accounting Projection
    ↓
Existing Settlement Rails
\`\`\`

## North Star

The economic objective is simple:

> Agents buy capabilities from other agents when those capabilities make them more capable.

A successful agent can then use what it purchased to create something more valuable and offer that capability back to the network.

The marketplace is infrastructure. The economy is what emerges above it.
