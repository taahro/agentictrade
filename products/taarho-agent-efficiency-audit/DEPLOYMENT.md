# Deployment and payment integration

## Current state

This product is an API MVP. The product code does not itself verify or collect payment. Do not expose the `/audit` endpoint as a paid public service until the payment gateway is configured and verified end to end.

## Local smoke test

From this directory:

```bash
python -m pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8080
```

In a second terminal, verify health:

```bash
curl http://127.0.0.1:8080/health
```

Send the included sample request:

```bash
curl -sS -X POST http://127.0.0.1:8080/audit \
  -H 'content-type: application/json' \
  --data @sample-request.json
```

## Marketplace integration

Follow [MARKETPLACE_REGISTRATION.md](MARKETPLACE_REGISTRATION.md) for the exact registry payload, proxy path, and verification gate.

Important network clarification: the existing `marketplace/payment.py` x402 implementation registers an EVM exact-payment scheme for **Base**. Use Base Sepolia (`eip155:84532`) for the initial test flow, and only consider Base mainnet (`eip155:8453`) after verification. The current implementation should not be described as an Arc payment integration unless the code and deployment configuration are explicitly changed and tested for Arc.

Before registering this endpoint:

1. Deploy the audit API behind HTTPS on a controlled host.
2. Configure the marketplace's receiving wallet and verify x402 middleware is actually enabled.
3. Register the service at the proposed `0.25` USDC per call with payment method `x402`.
4. Ensure the payment proxy verifies settlement before forwarding the paid request.
5. Complete a testnet payment and confirm the exact audit response is delivered only after successful payment.
6. Test invalid, missing, replayed, underpaid, and duplicate/idempotency requests.
7. Confirm wallet custody, fees, privacy terms, rate limits, monitoring, and settlement accounting before switching to mainnet.

Do not use production private keys in source code or commit them to GitHub. Use the deployment platform's secret manager. Do not describe testnet transactions as revenue. A service registry entry by itself does not prove checkout is operational.

## Price

The proposed pilot price is `0.25` USDC per audit. Treat it as a hypothesis, not a validated market price. The marketplace's platform fee and network costs reduce net proceeds; measure these before promising margins.

## Privacy

Trace inputs can contain sensitive operational data. Only accept traces the customer is authorized to share. Avoid storing request bodies by default, use HTTPS, set request-size limits, and publish a retention policy before onboarding customers.
