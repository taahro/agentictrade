# AgenticTrade marketplace registration runbook

This runbook connects the audit API to the existing AgenticTrade service registry and payment proxy. It is deliberately **manual and testnet-first**: it does not create keys, deploy the API, or move funds.

## Before registration

- [ ] Deploy the audit API behind HTTPS and confirm `GET /health` returns `200`.
- [ ] Keep `POST /audit` inaccessible directly to anonymous callers; the marketplace proxy must be the paid entry point.
- [ ] Configure the AgenticTrade host with a receiving wallet and working x402 middleware.
- [ ] Use **Base Sepolia** for initial verification (`NETWORK=eip155:84532`). The current x402 implementation in this repository targets Base, not Arc. Do not assume Arc support from hackathon copy.
- [ ] Create/use a provider API key and store it privately. Never paste secrets into GitHub, issues, chat, or a committed file.

## Register the service

The registry route is `POST /api/v1/services` and requires a provider API key. Use the AgenticTrade API's actual base URL, and replace placeholders locally.

```bash
export ACF_BASE_URL="https://YOUR-AGENTICTRADE-HOST"
export ACF_PROVIDER_KEY="KEY_ID:SECRET"
export TAARHO_AUDIT_ORIGIN="https://YOUR-AUDIT-HOST"

curl --fail-with-body -sS -X POST "$ACF_BASE_URL/api/v1/services" \
  -H "Authorization: Bearer $ACF_PROVIDER_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"Taarho Agent Efficiency Audit\",
    \"description\": \"Deterministic analysis of agent execution traces: latency, retries, failures, and caller-estimated cost.\",
    \"endpoint\": \"$TAARHO_AUDIT_ORIGIN\",
    \"price_per_call\": \"0.25\",
    \"category\": \"agent-tools\",
    \"tags\": [\"agent-efficiency\", \"trace-analysis\", \"latency\", \"retries\"],
    \"payment_method\": \"x402\",
    \"free_tier_calls\": 0
  }"
```

The endpoint is the **origin only** (for example, `https://audit.example`), not `/audit`, because the proxy appends the requested path.

Save the returned service `id`. The paid request path should be:

```text
POST $ACF_BASE_URL/api/v1/proxy/SERVICE_ID/audit
```

Send the same JSON payload as `products/taarho-agent-efficiency-audit/sample-request.json`. A buyer should use the marketplace's documented buyer authentication and x402 payment flow, not call the origin directly.

## Verification gate

Do not switch to mainnet or announce the listing as live until every check passes:

1. Confirm the service appears in public discovery with the intended name and price.
2. Confirm a request without payment is rejected with a payment challenge (or otherwise blocked by the configured gateway).
3. Complete a Base Sepolia test payment from a buyer agent.
4. Confirm the payment is verified and the exact audit response is delivered.
5. Confirm the transaction on the relevant Base Sepolia explorer and confirm marketplace usage records agree.
6. Test missing, invalid, underpaid, replayed, and duplicate/idempotency requests.
7. Confirm failed upstream calls do not silently become successful paid deliveries; inspect refund/retry behavior.
8. Verify provider settlement accounting and platform fees before any mainnet use.

If the gateway has no receiving wallet or x402 middleware is disabled, **stop**. A registry entry alone does not mean paid checkout is working.

## Pricing and scope

The proposed pilot price is `0.25` USDC per audit, not a market-validated price. The audit summarizes caller-supplied metrics and does not guarantee savings or independently verify vendor invoices. Review the marketplace's actual fee and settlement behavior before estimating net revenue.

## Security

- Use a trusted HTTPS host and keep request-size limits/rate limits enabled.
- Do not send API keys or wallet private keys in request bodies.
- Avoid storing raw traces by default; trace data can include confidential operational details.
- Never run a live-money verification test using a production wallet until the testnet path is proven.
