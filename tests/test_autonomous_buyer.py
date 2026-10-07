from decimal import Decimal

import pytest

from marketplace.agent_economy import CapabilityCandidate
from sdk.autonomous_buyer import AutonomousBuyerPolicy, PurchasePolicyError


def candidate(**overrides):
    values = {
        "service_id": "svc-1",
        "provider_id": "provider-1",
        "name": "Market Data",
        "description": "live market data",
        "category": "finance",
        "tags": ("market", "data"),
        "price": 0.005,
        "currency": "USDC",
    }
    values.update(overrides)
    return CapabilityCandidate(**values)


def test_candidate_policy_accepts_within_budget():
    policy = AutonomousBuyerPolicy(
        budget_usdc=Decimal("0.01"),
        max_payment_usdc=Decimal("0.01"),
    )
    policy.authorize_candidate(candidate())


def test_candidate_policy_rejects_over_per_payment_limit():
    policy = AutonomousBuyerPolicy(
        budget_usdc=Decimal("1"),
        max_payment_usdc=Decimal("0.01"),
    )
    with pytest.raises(PurchasePolicyError, match="candidate_exceeds_per_payment_limit"):
        policy.authorize_candidate(candidate(price=0.02))


def test_candidate_policy_rejects_provider():
    policy = AutonomousBuyerPolicy(
        budget_usdc=Decimal("1"),
        allowed_provider_ids=("trusted-provider",),
    )
    with pytest.raises(PurchasePolicyError, match="provider_not_allowed"):
        policy.authorize_candidate(candidate())


def test_x402_policy_accepts_base_sepolia_usdc():
    policy = AutonomousBuyerPolicy(
        budget_usdc=Decimal("0.02"),
        max_payment_usdc=Decimal("0.01"),
    )
    required = {
        "accepts": [
            {
                "scheme": "exact",
                "network": "eip155:84532",
                "amount": "5000",
                "payTo": "0xabc",
                "extra": {"name": "USDC", "version": "2"},
            }
        ]
    }
    policy.authorize_requirements(required)


def test_x402_policy_rejects_mainnet_by_default():
    policy = AutonomousBuyerPolicy(
        budget_usdc=Decimal("1"),
        max_payment_usdc=Decimal("0.01"),
    )
    required = {
        "accepts": [
            {
                "scheme": "exact",
                "network": "eip155:8453",
                "amount": "5000",
                "payTo": "0xabc",
                "extra": {"name": "USDC", "version": "2"},
            }
        ]
    }
    with pytest.raises(PurchasePolicyError, match="x402_payment_rejected_by_policy"):
        policy.authorize_requirements(required)


def test_x402_policy_rejects_unapproved_payee():
    policy = AutonomousBuyerPolicy(
        budget_usdc=Decimal("1"),
        max_payment_usdc=Decimal("0.01"),
        allowed_payees=("0xallowed",),
    )
    required = {
        "accepts": [
            {
                "scheme": "exact",
                "network": "eip155:84532",
                "amount": "5000",
                "payTo": "0xblocked",
                "extra": {"name": "USDC", "version": "2"},
            }
        ]
    }
    with pytest.raises(PurchasePolicyError, match="x402_payment_rejected_by_policy"):
        policy.authorize_requirements(required)


def test_x402_policy_supports_v1_amount_field():
    policy = AutonomousBuyerPolicy(
        budget_usdc=Decimal("0.02"),
        max_payment_usdc=Decimal("0.01"),
    )
    required = {
        "accepts": [
            {
                "scheme": "exact",
                "network": "eip155:84532",
                "maxAmountRequired": "10000",
                "payTo": "0xabc",
                "extra": {"name": "USDC", "version": "2"},
            }
        ]
    }
    policy.authorize_requirements(required)
