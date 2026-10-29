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

The parent Agent Commerce Framework supports service listings with a per-call price and x402 payment configuration. Before registering this endpoint:

1. Deploy the audit API behind HTTPS on a controlled host.
2. Configure the marketplace's receiving wallet and the chosen x402 network.
3. Register the service endpoint with a price of `0.25` USDC per call and payment method `x402`.
4. Ensure the payment proxy verifies settlement before forwarding the paid request.
5. Run a testnet transaction, confirm the service response is returned only after successful payment, and check the transaction in the relevant explorer.
6. Test invalid, missing, replayed, and underpaid payment headers.
7. Confirm production wallet custody, network fees, privacy terms, rate limits, and monitoring before switching to mainnet.

Do not use production private keys in source code or commit them to GitHub. Use the deployment platform's secret manager. Do not describe testnet transactions as revenue.

## Price

The proposed pilot price is `0.25` USDC per audit. Treat it as a hypothesis, not a validated market price. The marketplace's platform fee and network costs reduce net proceeds; measure these before promising margins.

## Privacy

Trace inputs can contain sensitive operational data. Only accept traces the customer is authorized to share. Avoid storing request bodies by default, use HTTPS, set request-size limits, and publish a retention policy before onboarding customers.
