from unittest.mock import Mock

from cognosphere.registration import publish_framework


def test_business_framework_maps_to_normal_agentictrade_service():
    registry = Mock()
    service = Mock()
    registry.register.return_value = service

    result = publish_framework(
        registry,
        provider_id="cognosphere-provider",
        base_url="https://agentictrade.example",
    )

    assert result is service
    kwargs = registry.register.call_args.kwargs
    assert kwargs["provider_id"] == "cognosphere-provider"
    assert kwargs["name"] == "Cognosphere Business Intelligence"
    assert kwargs["endpoint"].endswith(
        "/api/v1/cognosphere/frameworks/cognosphere.business.intelligence.v1"
    )
    assert kwargs["price_per_call"] == 10
    assert kwargs["payment_method"] == "nowpayments"
    assert kwargs["metadata"]["capability_id"] == "cognosphere.business.intelligence.v1"
