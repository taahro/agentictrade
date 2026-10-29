from app import AuditRequest, TraceEvent, audit


def test_audit_reports_failures_retries_and_cost():
    request = AuditRequest(events=[
        TraceEvent(tool="search", latency_ms=100, estimated_cost_usd=0.01, success=True, retry_count=0),
        TraceEvent(tool="browser", latency_ms=2000, estimated_cost_usd=0.03, success=False, retry_count=2),
    ], target_latency_ms=1000, target_cost_usd=0.05)

    result = audit(request)

    assert result["metrics"]["total_calls"] == 2
    assert result["metrics"]["failed_calls"] == 1
    assert result["metrics"]["total_retries"] == 2
    assert result["metrics"]["estimated_total_cost_usd"] == 0.04
    assert result["targets"]["latency_target_met"] is False
    assert result["targets"]["cost_target_met"] is True
    assert result["recommendations"]


def test_audit_handles_zero_cost_without_division_error():
    request = AuditRequest(events=[
        TraceEvent(tool="local-cache", latency_ms=10, estimated_cost_usd=0, success=True, retry_count=0)
    ])

    result = audit(request)

    assert result["metrics"]["estimated_cost_per_call_usd"] == 0
    assert result["metrics"]["failure_rate"] == 0
    assert result["recommendations"]
