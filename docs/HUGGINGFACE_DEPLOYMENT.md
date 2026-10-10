# Hugging Face Spaces deployment — AgenticTrade API

This branch prepares the existing FastAPI application for a Docker Space. It does **not** enable live payments or make the service production-ready by itself.

## What this deploys

- Existing FastAPI app: `api.main:app`
- Container listens on port `8000`; Space metadata declares `app_port: 8000`
- Existing marketplace, agent, payment-router, and Cognosphere routes from this branch

## Upload from this branch

1. Create a **new Docker Space** for the API. Keep it private while configuring and testing.
2. Clone or download the `deploy/huggingface-api-space` branch from GitHub.
3. Upload the repository contents to the Space repository, including the root `Dockerfile`, `README.md` (with Space metadata), application packages, templates, and `requirements.txt`.
4. Wait for the Docker build, then check the Space logs and `/health` endpoint.
5. Do not connect live payment credentials until the security checklist below is complete.

## Runtime secrets

Set these in the Space's **Settings → Variables and secrets** area, not in GitHub or browser code.

- `NOWPAYMENTS_API_KEY` — leave unset until payment-flow tests are ready.
- `NOWPAYMENTS_IPN_SECRET` — leave unset until a dedicated signed IPN receiver is implemented and tested.
- `DATABASE_URL` — use a managed PostgreSQL database for durable production data.
- `CORS_ORIGINS` — set to the exact trusted dashboard origin(s), comma-separated; do not use `*` for a credentialed production API.
- Configure other wallet/payment secrets only if the corresponding rail is intentionally enabled.

Never paste secret values into issues, pull requests, source files, screenshots, or chat messages.

## Persistence warning

The default SQLite database is not suitable for durable production state on an ephemeral Space filesystem. Use a managed persistent database before storing real agent identities, purchases, payment events, or settlement state. Backups and database access restrictions must be configured at the database provider.

## Payment safety gate

**Do not accept real purchases yet.** Before enabling NOWPayments:

1. Implement a dedicated public IPN endpoint; the existing `api/routes/webhooks.py` handles customer webhook subscriptions and is not itself a NOWPayments IPN receiver.
2. Verify `x-nowpayments-sig` against the raw request body using the configured IPN secret.
3. Validate the callback's payment ID, order ID, expected amount and currency against a locally created pending order. Do not trust callback fields alone.
4. Make event processing idempotent and reject conflicting/replayed state transitions.
5. Verify the payment with NOWPayments where appropriate and only release the purchased capability after a verified successful status.
6. Test valid, invalid-signature, duplicate, underpaid, wrong-currency, expired, and out-of-order notifications without real money.
7. Keep live payment creation disabled until the tests and end-to-end review pass.

## Deployment acceptance checklist

- [ ] Docker build succeeds from a clean Space
- [ ] `GET /health` responds successfully
- [ ] Database is external and persistent before real state is written
- [ ] Production CORS origins are explicitly set
- [ ] Administrative and agent write endpoints require authentication
- [ ] No secret is present in the uploaded repository or build logs
- [ ] NOWPayments IPN route and idempotency tests pass
- [ ] Sleep/uptime behavior is checked against the selected Space hardware
- [ ] Live transactions remain disabled until an explicit go-ahead

## Updating the Space

GitHub remains the source of truth. For each update, review and test a GitHub commit or pull request, then upload that approved revision to the Space. Do not make undocumented hotfixes directly in the Space repository.
