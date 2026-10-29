# Taarho Agent Efficiency Audit

**Product:** Agent Efficiency Audit  
**Publisher:** Taarho  
**Version:** 0.1.0 (MVP)  
**Suggested launch price:** US$0.25 per audit  
**Delivery:** JSON report over HTTP  
**Runtime cost model:** deterministic local analysis; no LLM API required

## The problem

AI-agent teams often cannot tell which tools, retries, and slow steps are consuming their time and budget. This service turns a structured execution trace into a concise, machine-readable efficiency report.

## What the buyer receives

- Total tool calls, failures, retries, estimated spend, and observed latency.
- Slowest tools and tools with the highest estimated spend.
- Failure and retry rates.
- Actionable recommendations ranked by estimated impact.
- A stable JSON response suitable for another agent to consume.

## Input

Send a JSON object containing an `events` array. Each event may include:

- `tool`: tool or step name.
- `latency_ms`: observed duration, non-negative number.
- `estimated_cost_usd`: estimated cost for that event, non-negative number.
- `success`: whether the step succeeded.
- `retry_count`: retries associated with the step, non-negative integer.

Only submit traces you are authorized to share. Do not include secrets, access tokens, personal data, or raw confidential prompts.

## Run locally

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn pydantic
cd products/taarho-agent-efficiency-audit
uvicorn app:app --host 127.0.0.1 --port 8080
```

Then open `/docs` locally or POST the sample payload below to `/audit`.

## Sample request

```json
{
  "events": [
    {"tool": "search", "latency_ms": 900, "estimated_cost_usd": 0.002, "success": true, "retry_count": 0},
    {"tool": "browser", "latency_ms": 2800, "estimated_cost_usd": 0.010, "success": true, "retry_count": 1},
    {"tool": "search", "latency_ms": 1100, "estimated_cost_usd": 0.002, "success": false, "retry_count": 2}
  ]
}
```

## Commercial model

Start with a suggested price of **$0.25 per audit**. Test demand with a small number of design partners before changing the price. This repository contains the analysis API, not a payment processor. List it behind the AgenticTrade payment proxy or another verified checkout; never claim a payment succeeded until the payment layer confirms settlement.

## Current limitations

- This MVP analyzes supplied measurements; it does not independently verify billing-provider invoices.
- Recommendations are heuristic, not guaranteed savings.
- No payment credentials or wallet private keys belong in this service.
- Run behind an authenticated payment gateway or add authentication before exposing it directly to the public internet.

## License

The parent repository is MIT-licensed. Confirm the repository's current licensing and any third-party dependencies before redistributing this package.
