from marketplace.agent_economy import (
    CapabilityCandidate, CapabilityOffer, CapabilityNeed,
    accept_offer, create_request, discover_candidates,
)


def test_discovery_ranks_matching_capability_and_filters_budget():
    need = CapabilityNeed(name="Market Data", category="data", tags=("forex", "realtime"), max_price=0.10)
    services = [
        {"id": "svc-weak", "provider_id": "agent-b", "name": "News Search", "category": "data",
         "tags": ["news"], "pricing": {"price_per_call": "0.05", "currency": "USDC"}},
        {"id": "svc-strong", "provider_id": "agent-c", "name": "Market Data", "category": "data",
         "tags": ["forex", "realtime"], "pricing": {"price_per_call": "0.02", "currency": "USDC"}},
        {"id": "svc-expensive", "provider_id": "agent-d", "name": "Market Data", "category": "data",
         "tags": ["forex", "realtime"], "pricing": {"price_per_call": "0.50", "currency": "USDC"}},
    ]
    assert [x.service_id for x in discover_candidates(need, services)] == ["svc-strong"]


def test_agent_to_agent_request_and_acceptance():
    need = CapabilityNeed(name="Risk Analysis", max_price=0.25)
    candidate = CapabilityCandidate(service_id="risk-1", provider_id="risk-agent",
                                     name="Risk Analysis", price=0.10)
    request = create_request("trading-agent", candidate, need, {"symbol": "AUD/JPY"})
    offer = CapabilityOffer(request_id=request.request_id, provider_id="risk-agent",
                            service_id="risk-1", price=0.08)
    receipt = accept_offer(request, offer, now="2026-10-06T00:00:00Z")
    assert receipt.status == "accepted"
    assert receipt.buyer_id == "trading-agent"
    assert receipt.provider_id == "risk-agent"
    assert receipt.price == 0.08


def test_self_purchase_is_rejected():
    need = CapabilityNeed(name="anything")
    candidate = CapabilityCandidate(service_id="svc", provider_id="same-agent",
                                     name="Anything", price=0.01)
    try:
        create_request("same-agent", candidate, need)
    except ValueError as exc:
        assert str(exc) == "buyer_provider_must_differ"
    else:
        raise AssertionError("self-purchase should fail")


def test_offer_over_budget_is_rejected():
    need = CapabilityNeed(name="anything", max_price=0.10)
    candidate = CapabilityCandidate(service_id="svc", provider_id="provider",
                                     name="Anything", price=0.05)
    request = create_request("buyer", candidate, need)
    offer = CapabilityOffer(request_id=request.request_id, provider_id="provider",
                            service_id="svc", price=0.11)
    try:
        accept_offer(request, offer)
    except ValueError as exc:
        assert str(exc) == "offer_exceeds_buyer_limit"
    else:
        raise AssertionError("over-budget offer should fail")
