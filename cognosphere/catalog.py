"""Cognosphere public framework catalog v1.

The catalog exposes only public abstractions and capability metadata.
It deliberately does not encode private Void architecture.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Tuple


@dataclass(frozen=True)
class FrameworkCard:
    framework_id: str
    name: str
    version: str
    domain: str
    purpose: str
    stages: Tuple[str, ...]
    inputs: Tuple[str, ...]
    outputs: Tuple[str, ...]
    capability_tags: Tuple[str, ...]
    price_usdc: Decimal
    risk_class: str = "general"

    def validate(self) -> None:
        for value in (self.framework_id, self.name, self.version, self.domain, self.purpose):
            if not value.strip():
                raise ValueError("framework_identity_required")
        if not self.stages or not self.inputs or not self.outputs:
            raise ValueError("framework_schema_required")
        if self.price_usdc < 0:
            raise ValueError("framework_price_negative")


COGNOSPHERE_V1 = (
    FrameworkCard(
        framework_id="cognosphere.systems.core.v1",
        name="Cognosphere Systems Core",
        version="1.0.0",
        domain="cross-domain",
        purpose="A reusable systems-thinking framework for structuring objectives, states, signals, relationships, transitions, constraints, decisions, feedback, and outcomes.",
        stages=(
            "define_objective",
            "map_system",
            "observe_state",
            "identify_signals",
            "evaluate_relationships",
            "detect_transition",
            "identify_missing_capabilities",
            "decide",
            "verify_outcome",
            "update_state",
        ),
        inputs=("objective", "entities", "observations", "constraints"),
        outputs=("system_model", "capability_requirements", "decision_context", "outcome_record"),
        capability_tags=("systems", "reasoning", "state", "transition", "decision", "agentic"),
        price_usdc=Decimal("5.00"),
    ),
    FrameworkCard(
        framework_id="cognosphere.business.intelligence.v1",
        name="Cognosphere Business Intelligence",
        version="1.0.0",
        domain="business",
        purpose="A structured framework for turning business objectives and market observations into capability requirements, decision contexts, actions, and measurable outcomes.",
        stages=(
            "define_business_objective",
            "map_market_and_entities",
            "assess_current_state",
            "identify_signals_and_constraints",
            "map_opportunities_and_risks",
            "identify_missing_capabilities",
            "evaluate_options",
            "form_action_plan",
            "measure_outcome",
            "adapt",
        ),
        inputs=("business_objective", "market_observations", "constraints", "available_capabilities"),
        outputs=("business_state", "opportunity_map", "capability_requirements", "decision_context", "action_plan", "outcome_metrics"),
        capability_tags=("business", "strategy", "market", "opportunity", "risk", "decision"),
        price_usdc=Decimal("10.00"),
    ),
    FrameworkCard(
        framework_id="cognosphere.marketing.intelligence.v1",
        name="Cognosphere Marketing Intelligence",
        version="1.0.0",
        domain="marketing",
        purpose="A structured framework for connecting audience signals, segmentation, messaging, response measurement, and adaptive marketing decisions.",
        stages=(
            "define_marketing_objective",
            "map_audience",
            "observe_behavior",
            "identify_segments",
            "map_signals",
            "form_message_hypotheses",
            "execute_test",
            "measure_response",
            "evaluate_outcome",
            "adapt",
        ),
        inputs=("marketing_objective", "audience_data", "behavior_signals", "constraints"),
        outputs=("audience_model", "segment_map", "message_hypotheses", "experiment_plan", "response_metrics", "next_actions"),
        capability_tags=("marketing", "audience", "segmentation", "messaging", "experimentation", "feedback"),
        price_usdc=Decimal("10.00"),
    ),
)

for _framework in COGNOSPHERE_V1:
    _framework.validate()
