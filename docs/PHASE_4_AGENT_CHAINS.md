# Phase 4 — Agent Capability Chains

Phase 4 turns individual capability purchases into composable agent-to-agent workflows.

## Core model

An agent starts with an objective and builds a dependency graph:

\`\`\`
Objective
   |
   +--> Market Data Agent
   |        |
   |        v
   +--> Risk Agent
   |        |
   |        v
   +--> Research Agent
            |
            v
        Decision Agent
\`\`\`

Each node is a capability purchase. A step may depend on one or more earlier steps, and its input can bind directly to a previous step's output.

The chain layer does not replace AgenticTrade discovery, negotiation, payment, x402, escrow, settlement, or reputation. It orchestrates those existing rails.

## Chain contracts

### CapabilityChainStep

A step contains:

- \`step_id\`
- \`CapabilityNeed\`
- explicit dependencies
- explicit input bindings

Bindings use deterministic references:

\`\`\`
$input.symbol
$input
$steps.market.output
$steps.market.output.price
\`\`\`

A step-output binding must also declare that step as a dependency. This prevents hidden edges in the graph.

### CapabilityChainPlan

A plan contains:

- buyer identity
- objective
- ordered step declarations
- chain currency
- optional maximum total spend
- optional metadata

Validation rejects duplicate IDs, unknown dependencies, cycles, currency mismatches, malformed budgets, and plans whose known per-step limits exceed the chain budget.

The execution order is deterministic topological ordering, so the same plan produces the same dependency sequence.

## Execution

\`CapabilityChainExecutor\` can run with:

1. an injected step runner for tests, simulations, or custom transports; or
2. an existing \`AutonomousCapabilityBuyer\`.

The executor passes each step's materialized payload to the buyer. The buyer remains responsible for:

- discovery
- candidate policy
- payment authorization
- CDP wallet handling
- x402 signing
- provider execution
- payment/settlement response handling

The chain executor records:

- completed steps
- step outputs
- step results
- receipts
- cumulative USDC spend
- failed step and failure reason

A failed step stops the chain. A step whose declared maximum cannot fit within the remaining chain budget is blocked before purchase.

## Example

A trading agent can subcontract specialized work:

\`\`\`python
from decimal import Decimal

from marketplace.agent_economy import CapabilityNeed
from marketplace.capability_chains import (
    CapabilityChainExecutor,
    CapabilityChainPlan,
    CapabilityChainStep,
)

plan = CapabilityChainPlan(
    buyer_id="trading-agent",
    objective="produce a risk-aware market decision",
    max_total_price=Decimal("0.02"),
    steps=(
        CapabilityChainStep(
            step_id="market",
            need=CapabilityNeed(
                name="Market Data",
                category="finance",
                max_price=0.005,
            ),
        ),
        CapabilityChainStep(
            step_id="risk",
            need=CapabilityNeed(
                name="Risk Analysis",
                category="finance",
                max_price=0.005,
            ),
            depends_on=("market",),
            input_bindings={
                "symbol": "$input.symbol",
                "market_data": "$steps.market.output",
            },
        ),
    ),
)

buyer = AutonomousCapabilityBuyer(
    agent_name="trading-agent",
    policy=AutonomousBuyerPolicy(
        budget_usdc=Decimal("0.02"),
        max_payment_usdc=Decimal("0.01"),
    ),
)

result = await CapabilityChainExecutor(buyer=buyer).execute(
    plan,
    {"symbol": "AUD/JPY"},
)
\`\`\`

The two specialist agents remain economically independent. The trading agent is the orchestrator and pays each provider according to the normal capability purchase flow.

## What Phase 4 establishes

Phase 4 now provides the composition substrate:

\`\`\`
Objective
  -> Plan
  -> Dependency graph
  -> Capability purchase
  -> Output handoff
  -> Next capability purchase
  -> Auditable chain result
\`\`\`

The next increments extend the chain runtime without creating another marketplace:

- result verification hooks and quality gates
- asynchronous/parallel branches for independent steps
- subcontracting policies and chain-level provider constraints
- composite capability publication, where an agent sells a finished outcome built from purchased capabilities
- chain-level reputation and cost/performance memory

This keeps the architecture aligned with the goal: agents can buy from agents because another specialist makes them more capable, then turn that improvement into a higher-value capability of their own.
