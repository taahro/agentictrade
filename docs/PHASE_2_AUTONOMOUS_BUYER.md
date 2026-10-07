# Phase 2 — Autonomous Buyer

Phase 2 connects the capability-economy substrate to a real autonomous buyer.

## Runtime

```
CapabilityNeed
   ↓
Marketplace discovery
   ↓
Deterministic candidate selection
   ↓
Buyer policy authorization
   ↓
CapabilityRequest
   ↓
Automatic marketplace-price Offer
   ↓
accept_offer()
   ↓
x402 402 preflight
   ↓
Policy checks: network / USDC / amount / payee
   ↓
CDP-managed wallet signs
   ↓
PAYMENT-SIGNATURE
   ↓
Provider execution
   ↓
Settlement receipt
```

Until Phase 3 adds provider-side quotation, the registered marketplace price is treated as the automatic quote. Phase 2 is therefore focused on the buyer side.

## Payment setup

Configure these environment variables or pass them to the buyer:

- `CDP_API_KEY_ID`
- `CDP_API_KEY_SECRET`
- `CDP_WALLET_SECRET`

The buyer creates or reuses a named CDP-managed EVM account. The AgenticTrade SDK does not store a private key.

Phase 2 defaults to Base Sepolia (`eip155:84532`) and USDC. Mainnet is opt-in through the policy.

## Example

```python
import asyncio
from decimal import Decimal

from marketplace.agent_economy import CapabilityNeed
from sdk.autonomous_buyer import AutonomousBuyerPolicy, AutonomousCapabilityBuyer

async def main():
    buyer = AutonomousCapabilityBuyer(
        agent_name="market-intelligence-agent",
        policy=AutonomousBuyerPolicy(
            budget_usdc=Decimal("0.10"),
            max_payment_usdc=Decimal("0.01"),
            allowed_networks=("eip155:84532",),
        ),
    )

    result = await buyer.purchase(
        CapabilityNeed(
            name="Market Data",
            category="finance",
            tags=("market", "data"),
            description="Current market data for a trading decision",
            max_price=0.01,
        ),
        payload={"symbol": "BTC/USD"},
    )

    print("success:", result.success)
    print("amount:", result.amount_usdc)
    print("tx:", result.transaction)

asyncio.run(main())
```

## Safety boundary

The model may formulate a CapabilityNeed, but payment authorization is deterministic. Phase 2 fails closed when the candidate or x402 payment violates the configured policy.

No private key is required. CDP manages the wallet signing path; x402 handles the HTTP 402 payment protocol. The buyer only signs an exact payment after policy checks pass.

## Next

Phase 3 moves quotation into the provider agent: machine-readable capability cards, delivery terms, expiry, SLA data, and provider-generated offers.
