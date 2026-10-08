from decimal import Decimal

import pytest

from marketplace.referrals import ReferralEngine, ReferralReview


def _review(**overrides):
    values = {
        "review_id": "review-1",
        "transaction_id": "tx-1",
        "referrer_id": "agent-referrer",
        "provider_id": "agent-provider",
        "capability_id": "capability-1",
        "rating": Decimal("4.5"),
        "verified_transaction": True,
        "verified_outcome": True,
    }
    values.update(overrides)
    return ReferralReview(**values)


def test_verified_review_qualifies():
    assert _review().qualifies_for_referral() is True


@pytest.mark.parametrize("field", ["verified_transaction", "verified_outcome"])
def test_unverified_activity_cannot_earn_referral(field):
    assert _review(**{field: False}).qualifies_for_referral() is False


def test_referral_credit_is_bounded_by_transaction():
    engine = ReferralEngine(reward_rate=Decimal("0.02"), max_credit=Decimal("5"))
    credit = engine.issue_credit(_review(), transaction_amount=Decimal("100"), credit_id="credit-1")
    assert credit.amount == Decimal("2.000000")
    assert credit.status == "available"


def test_referral_credit_respects_maximum():
    engine = ReferralEngine(reward_rate=Decimal("0.10"), max_credit=Decimal("3"))
    credit = engine.issue_credit(_review(), transaction_amount=Decimal("100"), credit_id="credit-2")
    assert credit.amount == Decimal("3.000000")


def test_unverified_review_cannot_issue_credit():
    engine = ReferralEngine()
    with pytest.raises(ValueError, match="verified"):
        engine.issue_credit(_review(verified_outcome=False), transaction_amount=Decimal("10"), credit_id="credit-3")


def test_credit_can_be_redeemed_against_next_purchase():
    engine = ReferralEngine(reward_rate=Decimal("0.02"))
    credit = engine.issue_credit(_review(), transaction_amount=Decimal("100"), credit_id="credit-4")
    updated, applied = engine.redeem(credit, purchase_amount=Decimal("50"))
    assert applied == Decimal("2.000000")
    assert updated.amount == Decimal("0.000000")
    assert updated.status == "redeemed"


def test_credit_cannot_be_redeemed_twice():
    engine = ReferralEngine()
    credit = engine.issue_credit(_review(), transaction_amount=Decimal("10"), credit_id="credit-5")
    redeemed, _ = engine.redeem(credit, purchase_amount=Decimal("10"))
    with pytest.raises(ValueError, match="not_available"):
        engine.redeem(redeemed, purchase_amount=Decimal("1"))
