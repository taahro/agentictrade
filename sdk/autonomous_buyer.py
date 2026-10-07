"""Phase 2 autonomous capability buyer.

The buyer side of the agent-to-agent capability economy:
discover -> evaluate -> request -> auto-accept -> authorize -> pay -> verify.

Payment uses the x402 Python client stack with a CDP-managed EVM wallet.
No private key is stored by this SDK.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

import httpx

from marketplace.agent_economy import (
    CapabilityCandidate,
    CapabilityNeed,
    CapabilityOffer,
    CapabilityReceipt,
    CapabilityRequest,
    accept_offer,
    create_request,
    discover_candidates,
)

DEFAULT_X402_NETWORK = "eip155:84532"
USDC_DECIMALS = 6


class AutonomousBuyerError(RuntimeError):
    """Raised when autonomous purchasing cannot proceed."""


class PurchasePolicyError(AutonomousBuyerError):
    """Raised when a capability or payment violates buyer policy."""


@dataclass(frozen=True)
class AutonomousBuyerPolicy:
    """Fail-closed policy for autonomous capability purchases."""

    budget_usdc: Decimal
    max_payment_usdc: Decimal = Decimal("0.01")
    allowed_networks: tuple[str, ...] = (DEFAULT_X402_NETWORK,)
    allowed_provider_ids: tuple[str, ...] = ()
    allowed_payees: tuple[str, ...] = ()
    require_usdc: bool = True

    def authorize_candidate(self, candidate: CapabilityCandidate) -> None:
        """Authorize a selected marketplace candidate before any payment occurs."""
        currency = candidate.currency.upper()
        if self.require_usdc and currency != "USDC":
            raise PurchasePolicyError("candidate_currency_not_allowed")

        try:
            price = Decimal(str(candidate.price))
        except (InvalidOperation, ValueError) as exc:
            raise PurchasePolicyError("candidate_price_invalid") from exc

        if price < 0:
            raise PurchasePolicyError("candidate_price_invalid")
        if price > self.max_payment_usdc:
            raise PurchasePolicyError("candidate_exceeds_per_payment_limit")
        if self.budget_usdc > 0 and price > self.budget_usdc:
            raise PurchasePolicyError("candidate_exceeds_budget")

        if self.allowed_provider_ids and candidate.provider_id not in self.allowed_provider_ids:
            raise PurchasePolicyError("provider_not_allowed")

    def authorize_requirements(self, payment_required: Any) -> None:
        """Validate x402 payment requirements before any signature is created."""
        accepts = getattr(payment_required, "accepts", None)
        if accepts is None and isinstance(payment_required, Mapping):
            accepts = payment_required.get("accepts")
        accepts = list(accepts or [])

        if not accepts:
            raise PurchasePolicyError("x402_no_payment_options")

        allowed = []
        for req in accepts:
            item = _to_mapping(req)
            scheme = str(item.get("scheme", "")).lower()
            network = str(item.get("network", ""))

            if scheme != "exact" or network not in self.allowed_networks:
                continue

            if self.require_usdc:
                extra = item.get("extra") or {}
                if str(extra.get("name", "")).upper() != "USDC":
                    continue

            amount_raw = item.get("amount", item.get("maxAmountRequired", "0"))
            try:
                amount = Decimal(str(amount_raw)) / (Decimal(10) ** USDC_DECIMALS)
            except (InvalidOperation, ValueError) as exc:
                raise PurchasePolicyError("x402_amount_invalid") from exc

            if amount > self.max_payment_usdc:
                continue
            if self.budget_usdc > 0 and amount > self.budget_usdc:
                continue

            pay_to = str(item.get("payTo", item.get("pay_to", "")))
            if self.allowed_payees and pay_to.lower() not in {p.lower() for p in self.allowed_payees}:
                continue

            allowed.append(item)

        if not allowed:
            raise PurchasePolicyError("x402_payment_rejected_by_policy")


@dataclass(frozen=True)
class CapabilityPurchaseResult:
    """Auditable result of a Phase 2 capability purchase."""

    success: bool
    candidate: CapabilityCandidate
    request: CapabilityRequest
    offer: CapabilityOffer
    receipt: CapabilityReceipt
    response: Any = None
    transaction: str | None = None
    amount_usdc: str = "0"
    error: str = ""


class AutonomousCapabilityBuyer:
    """Phase 2 buyer: autonomous capability selection plus x402 execution."""

    def __init__(
        self,
        *,
        agent_name: str = "autonomous-capability-buyer",
        marketplace_url: str | None = None,
        api_key: str | None = None,
        owner_email: str = "",
        cdp_api_key_id: str | None = None,
        cdp_api_key_secret: str | None = None,
        cdp_wallet_secret: str | None = None,
        wallet_name: str = "agentictrade-capability-buyer",
        policy: AutonomousBuyerPolicy | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.agent_name = agent_name
        self.marketplace_url = (
            marketplace_url or os.environ.get("AGENTICTRADE_URL") or "https://agentictrade.io"
        ).rstrip("/")
        self._api_key = api_key or os.environ.get("AGENTICTRADE_API_KEY")
        self.owner_email = owner_email
        self.cdp_api_key_id = cdp_api_key_id or os.environ.get("CDP_API_KEY_ID")
        self.cdp_api_key_secret = cdp_api_key_secret or os.environ.get("CDP_API_KEY_SECRET")
        self.cdp_wallet_secret = cdp_wallet_secret or os.environ.get("CDP_WALLET_SECRET")
        self.wallet_name = wallet_name
        self.policy = policy or AutonomousBuyerPolicy(
            budget_usdc=Decimal("0"),
            max_payment_usdc=Decimal("0.01"),
        )
        self.timeout = timeout
        self._agent_id: str | None = None
        self._spent_usdc = Decimal("0")

    @property
    def agent_id(self) -> str | None:
        return self._agent_id

    @property
    def total_spent_usdc(self) -> Decimal:
        return self._spent_usdc

    @property
    def budget_remaining_usdc(self) -> Decimal | None:
        if self.policy.budget_usdc <= 0:
            return None
        return max(Decimal("0"), self.policy.budget_usdc - self._spent_usdc)

    async def discover(self, need: CapabilityNeed) -> list[CapabilityCandidate]:
        """Discover and deterministically rank candidates for a capability need."""
        params: dict[str, str] = {"q": need.name}
        if need.category:
            params["category"] = need.category
        if need.max_price is not None:
            params["max_price"] = str(need.max_price)

        async with httpx.AsyncClient(base_url=self.marketplace_url, timeout=self.timeout) as client:
            response = await client.get(
                "/api/v1/discover",
                headers=self._headers(),
                params=params,
            )
            response.raise_for_status()
            data = response.json()

        services = data.get("services", data if isinstance(data, list) else [])
        return discover_candidates(need, services)

    async def purchase(
        self,
        need: CapabilityNeed,
        payload: Mapping[str, Any] | None = None,
        *,
        path: str = "/call",
        method: str = "POST",
    ) -> CapabilityPurchaseResult:
        """Buy the best allowed capability candidate and execute it."""
        wallet_address = await self._wallet_address()
        await self._ensure_onboarded(wallet_address)

        effective_need = need
        if effective_need.max_price is None and self.policy.budget_usdc > 0:
            effective_need = CapabilityNeed(
                name=need.name,
                description=need.description,
                category=need.category,
                tags=need.tags,
                input_schema=need.input_schema,
                output_schema=need.output_schema,
                max_price=self.policy.budget_usdc,
                currency=need.currency,
            )

        candidates = await self.discover(effective_need)
        if not candidates:
            raise AutonomousBuyerError("no_capability_candidate")

        candidate = next(
            (c for c in candidates if c.currency.upper() == effective_need.currency.upper()),
            None,
        )
        if candidate is None:
            raise PurchasePolicyError("no_candidate_matches_currency")

        self.policy.authorize_candidate(candidate)

        request = create_request(
            buyer_id=self._agent_id or wallet_address,
            candidate=candidate,
            need=effective_need,
            input_data=payload or {},
        )

        # Until Phase 3 exposes provider-side quoting, the marketplace price
        # acts as the automatic quote accepted by the buyer policy.
        offer = CapabilityOffer(
            request_id=request.request_id,
            provider_id=candidate.provider_id,
            service_id=candidate.service_id,
            price=candidate.price,
            currency=candidate.currency,
        )
        receipt = accept_offer(request, offer)

        result = await self._execute_paid_call(
            candidate=candidate,
            receipt=receipt,
            payload=payload or {},
            path=path,
            method=method,
        )
        if result.success:
            self._spent_usdc += Decimal(result.amount_usdc)
        return result

    async def _execute_paid_call(
        self,
        *,
        candidate: CapabilityCandidate,
        receipt: CapabilityReceipt,
        payload: Mapping[str, Any],
        path: str,
        method: str,
    ) -> CapabilityPurchaseResult:
        """Execute one x402-protected request with pre-sign policy checks."""
        try:
            from cdp import CdpClient
            from cdp.evm_local_account import EvmLocalAccount
            from x402 import x402ClientSync
            from x402.http import x402HTTPClient
            from x402.mechanisms.evm import EthAccountSigner
            from x402.mechanisms.evm.exact import ExactEvmScheme
        except ImportError as exc:
            raise AutonomousBuyerError(
                "Phase 2 payment dependencies missing. Install "
                "agent-commerce-framework[x402]."
            ) from exc

        if not self.cdp_api_key_id or not self.cdp_api_key_secret:
            raise AutonomousBuyerError("CDP_API_KEY_ID_AND_SECRET_REQUIRED")
        if not self.cdp_wallet_secret:
            raise AutonomousBuyerError("CDP_WALLET_SECRET_REQUIRED")

        url = (
            f"{self.marketplace_url}/api/v1/proxy/"
            f"{candidate.service_id}/{path.lstrip('/')}"
        )

        async with CdpClient(
            api_key_id=self.cdp_api_key_id,
            api_key_secret=self.cdp_api_key_secret,
            wallet_secret=self.cdp_wallet_secret,
        ) as cdp:
            account = await cdp.evm.get_or_create_account(name=self.wallet_name)
            signer = EthAccountSigner(EvmLocalAccount(account))
            payment_client = x402ClientSync()
            for network in self.policy.allowed_networks:
                payment_client.register(network, ExactEvmScheme(signer))
            x402_http = x402HTTPClient(payment_client)

            async with httpx.AsyncClient(timeout=self.timeout) as http:
                headers = self._headers()
                response = await http.request(
                    method, url, headers=headers, json=dict(payload)
                )

                if response.status_code != 402:
                    return self._result_without_payment(
                        response=response,
                        candidate=candidate,
                        receipt=receipt,
                    )

                try:
                    body = response.json()
                except ValueError:
                    body = None

                payment_required = x402_http.get_payment_required_response(
                    response.headers.get, body
                )
                self.policy.authorize_requirements(payment_required)

                payment_payload = payment_client.create_payment_payload(payment_required)
                payment_headers = x402_http.encode_payment_signature_header(
                    payment_payload
                )

                paid_response = await http.request(
                    method,
                    url,
                    headers={**headers, **payment_headers},
                    json=dict(payload),
                )

                x402_http.process_payment_result(
                    payment_payload,
                    paid_response.headers.get,
                    paid_response.status_code,
                )

                transaction = None
                try:
                    settled = x402_http.get_payment_settle_response(
                        paid_response.headers.get
                    )
                    transaction = getattr(settled, "transaction", None)
                except (AttributeError, ValueError):
                    transaction = (
                        paid_response.headers.get("payment-response")
                        or paid_response.headers.get("x-payment-transaction")
                    )

                return self._result_from_response(
                    response=paid_response,
                    candidate=candidate,
                    receipt=receipt,
                    transaction=transaction,
                )

    def _result_without_payment(
        self,
        *,
        response: httpx.Response,
        candidate: CapabilityCandidate,
        receipt: CapabilityReceipt,
    ) -> CapabilityPurchaseResult:
        data = self._decode(response)
        if 200 <= response.status_code < 300:
            return CapabilityPurchaseResult(
                success=True,
                candidate=candidate,
                request=_request_from_receipt(receipt),
                offer=_offer_from_receipt(receipt),
                receipt=receipt,
                response=data,
                amount_usdc="0",
            )
        return CapabilityPurchaseResult(
            success=False,
            candidate=candidate,
            request=_request_from_receipt(receipt),
            offer=_offer_from_receipt(receipt),
            receipt=receipt,
            response=data,
            amount_usdc="0",
            error=f"HTTP {response.status_code}",
        )

    def _result_from_response(
        self,
        *,
        response: httpx.Response,
        candidate: CapabilityCandidate,
        receipt: CapabilityReceipt,
        transaction: str | None,
    ) -> CapabilityPurchaseResult:
        data = self._decode(response)
        amount = Decimal(str(receipt.price))
        success = 200 <= response.status_code < 300
        return CapabilityPurchaseResult(
            success=success,
            candidate=candidate,
            request=_request_from_receipt(receipt),
            offer=_offer_from_receipt(receipt),
            receipt=receipt,
            response=data,
            transaction=transaction,
            amount_usdc=str(amount),
            error="" if success else f"HTTP {response.status_code}",
        )

    async def _wallet_address(self) -> str:
        """Provision or load the CDP EVM wallet and return its address."""
        try:
            from cdp import CdpClient
        except ImportError as exc:
            raise AutonomousBuyerError(
                "Phase 2 payment dependencies missing. Install "
                "agent-commerce-framework[x402]."
            ) from exc

        if not self.cdp_api_key_id or not self.cdp_api_key_secret:
            raise AutonomousBuyerError("CDP_API_KEY_ID_AND_SECRET_REQUIRED")
        if not self.cdp_wallet_secret:
            raise AutonomousBuyerError("CDP_WALLET_SECRET_REQUIRED")

        async with CdpClient(
            api_key_id=self.cdp_api_key_id,
            api_key_secret=self.cdp_api_key_secret,
            wallet_secret=self.cdp_wallet_secret,
        ) as cdp:
            account = await cdp.evm.get_or_create_account(name=self.wallet_name)
            return str(account.address)

    async def _ensure_onboarded(self, wallet_address: str) -> None:
        if self._api_key and self._agent_id:
            return

        payload = {
            "agent_name": self.agent_name,
            "role": "buyer",
            "wallet_address": wallet_address,
            "owner_email": self.owner_email,
            "budget_limit_usdc": (
                str(self.policy.budget_usdc) if self.policy.budget_usdc > 0 else ""
            ),
        }

        async with httpx.AsyncClient(
            base_url=self.marketplace_url, timeout=self.timeout
        ) as client:
            response = await client.post(
                "/api/v1/agents/onboard",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            if response.status_code >= 400:
                raise AutonomousBuyerError(
                    f"Buyer onboard failed: {response.text[:300]}"
                )
            data = response.json()

        self._agent_id = data["agent_id"]
        self._api_key = data["api_key"]

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    @staticmethod
    def _decode(response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return {"body": response.text, "status_code": response.status_code}


def _to_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "model_dump"):
        return dict(value.model_dump(by_alias=True))
    if hasattr(value, "dict"):
        return dict(value.dict())
    return {
        name: getattr(value, name)
        for name in (
            "scheme",
            "network",
            "amount",
            "maxAmountRequired",
            "asset",
            "payTo",
            "extra",
        )
        if hasattr(value, name)
    }


def _request_from_receipt(receipt: CapabilityReceipt) -> CapabilityRequest:
    return CapabilityRequest(
        request_id=receipt.request_id,
        buyer_id=receipt.buyer_id,
        provider_id=receipt.provider_id,
        service_id=receipt.service_id,
        need=CapabilityNeed(
            name="purchased-capability",
            currency=receipt.currency,
        ),
        input={},
        created_at=receipt.issued_at,
    )


def _offer_from_receipt(receipt: CapabilityReceipt) -> CapabilityOffer:
    return CapabilityOffer(
        request_id=receipt.request_id,
        provider_id=receipt.provider_id,
        service_id=receipt.service_id,
        price=receipt.price,
        currency=receipt.currency,
    )
