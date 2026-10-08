# Payment Rails

AgenticTrade keeps payment providers behind the existing PaymentProvider interface.
The agent economy does not depend on a specific payment vendor.

## Active development rail: NOWPayments

NOWPayments is the currently available crypto payment rail.

Configuration:
- NOWPAYMENTS_API_KEY
- NOWPAYMENTS_IPN_SECRET
- NOWPAYMENTS_SANDBOX=true for development where supported

The existing provider handles payment creation, status lookup, payment detail retrieval,
and IPN HMAC-SHA512 verification.

Secrets must remain in environment or secret storage and must never be committed.

## Future rail: Coinbase CDP

The autonomous buyer already contains the CDP/x402 path. It remains available but
inactive until the required CDP credentials are configured.

The two rails share the same economic boundary:

    Agent Economy
         |
    PaymentProvider
      /           NOWPayments  CDP/x402

Agents request a payment outcome rather than knowing which provider implements it.

## Referral incentives

Verified capability outcomes may create referral credits. A review qualifies only when
the underlying transaction is verified and the delivered capability outcome is verified.

Credits are accounting/incentive objects until a payment rail is explicitly used to settle
an external reward. They must not create value from nothing.

## First economic milestone

    Buyer Agent
       -> discover capability
       -> evaluate provider
       -> request quote
       -> create payment
       -> verify payment
       -> execute capability
       -> verify outcome
       -> record reputation
       -> issue eligible referral credit

This keeps the economic model provider-neutral while allowing the currently available
payment rail to be exercised now.
