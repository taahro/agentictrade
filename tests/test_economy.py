from decimal import Decimal

import pytest

from marketplace.economy import (
    CapabilityOutcome,
    CompositeCapability,
    DynamicPricingPolicy,
    EconomyLedger,
    OutcomeReputationPolicy,
    ReferralPolicy,
)


def test_outcome_reputation_is_bounded_and_verification_aware():
    policy = OutcomeReputationPolicy()
    good = CapabilityOutcome(
        capability_id="cap-risk",
        provider_id="risk-agent",
        buyer_id="trading-agent",
        success=True,
        quality_score=Decimal("9"),
        value_score=Decimal("8"),
        latency_ms=500,
        price=Decimal("0.005"),
        verified=True,
    )
    score = policy.score(good)
    assert score == Decimal("9.15")
    assert Decimal("0") <= score <= Decimal("10")

    unverified = CapabilityOutcome(
        capability_id="cap-risk",
        provider_id="risk-agent",
        buyer_id="trading-agent",
        success=True,
        quality_score=Decimal("9"),
        value_score=Decimal("10"),
        latency_ms=500,
        verified=False,
    )
    assert policy.score(unverified) < score


def test_outcome_validation_rejects_bad_scores():
    with pytest.raises(ValueError, match="quality_score_out_of_range"):
        CapabilityOutcome(
            capability_id="cap",
            provider_id="provider",
            buyer_id="buyer",
            quality_score=Decimal("11"),
        ).validate()


def test_dynamic_pricing_stays_within_explicit_bounds():
    policy = DynamicPricingPolicy(
        base_price=Decimal("0.01"),
        min_price=Decimal("0.006"),
        max_price=Decimal("0.015"),
    )
    low = policy.quote(utilization=0, reputation=0, demand=0)
    high = policy.quote(utilization=10, reputation=10, demand=10)

    assert low == Decimal("0.006")
    assert high == Decimal("0.015")


def test_referral_reward_is_bounded():
    policy = ReferralPolicy(reward_rate=Decimal("0.10"), max_reward=Decimal("0.02"))
    assert policy.reward("0.50") == Decimal("0.020000")


def test_composite_capability_has_explicit_provenance():
    composite = CompositeCapability(
        capability_id="cap-trading-decision-v1",
        provider_id="decision-agent",
        service_id="decision-service",
        name="Risk-Aware Trading Decision",
        component_capability_ids=("cap-market", "cap-risk", "cap-research"),
        price=Decimal("0.025"),
        provenance={
            "composition": "agent-chain",
            "source_chain_id": "chain_123",
        },
    )
    data = composite.as_dict()
    assert data["component_capability_ids"] == [
        "cap-market",
        "cap-risk",
        "cap-research",
    ]
    assert data["provenance"]["source_chain_id"] == "chain_123"


def test_economy_ledger_accounts_for_purchase_fee_and_referral():
    ledger = EconomyLedger()
    entries = ledger.record_purchase(
        buyer_id="buyer",
        provider_id="provider",
        amount=Decimal("1.00"),
        platform_fee=Decimal("0.10"),
        referral_id="referrer",
        referral_policy=ReferralPolicy(reward_rate=Decimal("0.02")),
        transaction_id="tx-1",
        reference_id="receipt-1",
    )

    assert len(entries) == 4
    assert ledger.balance("buyer") == Decimal("-1.00")
    assert ledger.balance("provider") == Decimal("0.88")
    assert ledger.balance("referrer") == Decimal("0.02")
    assert ledger.balance("agentictrade") == Decimal("0.10")


def test_ledger_rejects_fee_above_purchase():
    with pytest.raises(ValueError, match="purchase_amount_invalid"):
        EconomyLedger().record_purchase(
            buyer_id="buyer",
            provider_id="provider",
            amount="0.01",
            platform_fee="0.02",
        )


def test_ledger_rejects_unauthorized_referral_value_creation():
    with pytest.raises(ValueError, match="referral_reward_exceeds_provider_revenue"):
        EconomyLedger().record_purchase(
            buyer_id="buyer",
            provider_id="provider",
            amount="0.01",
            platform_fee="0.01",
            referral_id="referrer",
            referral_policy=ReferralPolicy(reward_rate="0.02"),
        )
