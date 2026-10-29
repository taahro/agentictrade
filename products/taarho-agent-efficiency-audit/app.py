"""Taarho Agent Efficiency Audit: deterministic trace analytics MVP.

This API does not handle payments. Put it behind an authenticated gateway or
the AgenticTrade payment proxy before public deployment.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field, ConfigDict

app = FastAPI(
    title="Taarho Agent Efficiency Audit",
    version="0.1.0",
    description="Analyze agent execution traces and return a deterministic efficiency report.",
)


class TraceEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: str = Field(min_length=1, max_length=120)
    latency_ms: float = Field(default=0, ge=0, le=86_400_000)
    estimated_cost_usd: float = Field(default=0, ge=0, le=1_000_000)
    success: bool = True
    retry_count: int = Field(default=0, ge=0, le=1000)


class AuditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: list[TraceEvent] = Field(min_length=1, max_length=10_000)
    target_latency_ms: Optional[float] = Field(default=None, gt=0)
    target_cost_usd: Optional[float] = Field(default=None, gt=0)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "product": "taarho-agent-efficiency-audit", "version": "0.1.0"}


@app.post("/audit")
def audit(payload: AuditRequest) -> dict:
    events = payload.events
    total_calls = len(events)
    failures = sum(not event.success for event in events)
    retries = sum(event.retry_count for event in events)
    total_latency = sum(event.latency_ms for event in events)
    total_cost = sum(event.estimated_cost_usd for event in events)
    by_tool: dict[str, dict] = defaultdict(
        lambda: {"calls": 0, "failures": 0, "retries": 0, "latency_ms": 0.0, "cost_usd": 0.0}
    )

    for event in events:
        item = by_tool[event.tool]
        item["calls"] += 1
        item["failures"] += int(not event.success)
        item["retries"] += event.retry_count
        item["latency_ms"] += event.latency_ms
        item["cost_usd"] += event.estimated_cost_usd

    tool_report = []
    for name, item in by_tool.items():
        calls = item["calls"]
        tool_report.append({
            "tool": name,
            **item,
            "average_latency_ms": round(item["latency_ms"] / calls, 2),
            "failure_rate": round(item["failures"] / calls, 4),
        })

    slowest = sorted(tool_report, key=lambda item: item["average_latency_ms"], reverse=True)[:3]
    costliest = sorted(tool_report, key=lambda item: item["cost_usd"], reverse=True)[:3]
    recommendations = []

    if failures:
        recommendations.append({
            "priority": "high",
            "finding": f"{failures} of {total_calls} calls failed ({failures / total_calls:.1%}).",
            "action": "Inspect failed-call traces and add bounded retries with backoff only for transient errors.",
        })
    if retries:
        recommendations.append({
            "priority": "medium",
            "finding": f"{retries} retries were reported across {total_calls} calls.",
            "action": "Check whether repeated calls can be cached, deduplicated, or replaced with a single batched request.",
        })
    if slowest and slowest[0]["average_latency_ms"] > 1000:
        recommendations.append({
            "priority": "medium",
            "finding": f"'{slowest[0]['tool']}' has the highest average latency ({slowest[0]['average_latency_ms']} ms).",
            "action": "Profile this step first; consider smaller outputs, parallel independent work, or a faster endpoint.",
        })
    if costliest and total_cost > 0 and costliest[0]["cost_usd"] / total_cost >= 0.5:
        recommendations.append({
            "priority": "medium",
            "finding": f"'{costliest[0]['tool']}' accounts for at least half of the estimated trace cost.",
            "action": "Review model/tool choice, prompt size, caching, and whether the step needs to run on every request.",
        })
    if not recommendations:
        recommendations.append({
            "priority": "info",
            "finding": "No high-signal failure, retry, latency, or cost concentration was detected by the MVP rules.",
            "action": "Collect a larger representative sample and compare repeated runs before concluding the workflow is efficient.",
        })

    result = {
        "product": "taarho-agent-efficiency-audit",
        "version": "0.1.0",
        "metrics": {
            "total_calls": total_calls,
            "unique_tools": len(by_tool),
            "failed_calls": failures,
            "failure_rate": round(failures / total_calls, 4),
            "total_retries": retries,
            "total_observed_latency_ms": round(total_latency, 2),
            "average_latency_per_call_ms": round(total_latency / total_calls, 2),
            "estimated_total_cost_usd": round(total_cost, 6),
            "estimated_cost_per_call_usd": round(total_cost / total_calls, 6),
        },
        "tool_breakdown": sorted(tool_report, key=lambda item: item["tool"]),
        "slowest_tools": slowest,
        "costliest_tools": costliest,
        "recommendations": recommendations,
        "targets": {
            "target_latency_ms": payload.target_latency_ms,
            "target_cost_usd": payload.target_cost_usd,
            "latency_target_met": (
                total_latency / total_calls <= payload.target_latency_ms
                if payload.target_latency_ms is not None else None
            ),
            "cost_target_met": (
                total_cost <= payload.target_cost_usd
                if payload.target_cost_usd is not None else None
            ),
        },
        "disclaimer": "Cost figures are caller-supplied estimates; recommendations are heuristic and do not guarantee savings.",
    }
    return result
