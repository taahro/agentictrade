"""Verified referral and review primitives for the agent economy.

Referral rewards are earned only from a completed capability transaction and a
verified outcome. The module records incentive eligibility; payment rails remain
responsible for moving any actual reward.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decimal(value: Decimal | str | float | int) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("decimal_invalid") from exc
    if not result.is_finite():
        raise ValueError("decimal_invalid")
    return result


@dataclass(frozen=True)
class ReferralReview:
    """A review that can qualify an agent for a referral incentive."""

    review_id: str
    transaction_id: str
    referrer_id: str
    provider_id: str
    capability_id: str
    rating: Decimal
    verified_transaction: bool
    verified_outcome: bool
    created_at: str = field(default_factory=_utcnow)

    def validate(self) -> None:
        for name, value in (
            ("review_id", self.review_id),
            ("transaction_id", self.transaction_id),
            ("referrer_id", self.referrer_id),
            ("provider_id", self.provider_id),
            ("capability_id", self.capability_id),
        ):
            if not value.strip():
                raise ValueError(f"{name}_required")
        rating = _decimal(self.rating)
        if rating < 0 or rating > 5:
            raise ValueError("rating_out_of_range")

    def qualifies_for_referral(self) -> bool:
        self.validate()
        return self.verified_transaction and self.verified_outcome


@dataclass(frozen=True)
class ReferralCredit:
    """A bounded, non-custodial credit for a future capability purchase."""

    credit_id: str
    agent_id: str
    source_review_id: str
    amount: Decimal
    currency: str = "USDC"
    status: str = "available"
    created_at: str = field(default_factory=_utcnow)

    def validate(self) -> None:
        if not self.credit_id.strip() or not self.agent_id.strip():
            raise ValueError("referral_credit_identity_required")
        if not self.source_review_id.strip():
            raise ValueError("referral_credit_source_required")
        if _decimal(self.amount) < 0:
            raise ValueError("referral_credit_negative")
        if not self.currency.strip():
            raise ValueError("referral_credit_currency_required")
        if self.status not in {"available", "redeemed", "expired", "revoked"}:
            raise ValueError("referral_credit_status_invalid")


class ReferralEngine:
    """Issue referral credits only after verified economic activity."""

    def __init__(self, reward_rate: Decimal = Decimal("0.02"), max_credit: Decimal | None = None):
        self.reward_rate = _decimal(reward_rate)
        self.max_credit = None if max_credit is None else _decimal(max_credit)
        if self.reward_rate < 0 or self.reward_rate > 1:
            raise ValueError("reward_rate_out_of_range")
        if self.max_credit is not None and self.max_credit < 0:
            raise ValueError("max_credit_negative")

    def issue_credit(
        self,
        review: ReferralReview,
        *,
        transaction_amount: Decimal | str | float,
        credit_id: str,
    ) -> ReferralCredit:
        if not review.qualifies_for_referral():
            raise ValueError("referral_requires_verified_transaction_and_outcome")

        amount = _decimal(transaction_amount)
        if amount < 0:
            raise ValueError("transaction_amount_negative")

        credit = amount * self.reward_rate
        if self.max_credit is not None:
            credit = min(credit, self.max_credit)

        result = ReferralCredit(
            credit_id=credit_id,
            agent_id=review.referrer_id,
            source_review_id=review.review_id,
            amount=credit.quantize(Decimal("0.000001")),
        )
        result.validate()
        return result

    def redeem(
        self,
        credit: ReferralCredit,
        *,
        purchase_amount: Decimal | str | float,
    ) -> tuple[ReferralCredit, Decimal]:
        credit.validate()
        if credit.status != "available":
            raise ValueError("referral_credit_not_available")

        purchase = _decimal(purchase_amount)
        if purchase < 0:
            raise ValueError("purchase_amount_negative")

        applied = min(credit.amount, purchase)
        remaining = credit.amount - applied
        status = "redeemed" if applied == credit.amount else "available"

        updated = ReferralCredit(
            credit_id=credit.credit_id,
            agent_id=credit.agent_id,
            source_review_id=credit.source_review_id,
            amount=remaining,
            currency=credit.currency,
            status=status,
            created_at=credit.created_at,
        )
        updated.validate()
        return updated, applied
