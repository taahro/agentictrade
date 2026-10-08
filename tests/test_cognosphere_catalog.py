from decimal import Decimal

from cognosphere import COGNOSPHERE_V1


def test_cognosphere_v1_contains_three_launch_frameworks():
    ids = {framework.framework_id for framework in COGNOSPHERE_V1}
    assert ids == {
        "cognosphere.systems.core.v1",
        "cognosphere.business.intelligence.v1",
        "cognosphere.marketing.intelligence.v1",
    }


def test_frameworks_are_machine_readable_and_priced():
    for framework in COGNOSPHERE_V1:
        framework.validate()
        assert framework.inputs
        assert framework.outputs
        assert framework.stages
        assert framework.price_usdc >= Decimal("0")


def test_business_is_first_sale_candidate():
    business = next(
        item for item in COGNOSPHERE_V1
        if item.framework_id == "cognosphere.business.intelligence.v1"
    )
    assert business.price_usdc == Decimal("10.00")
    assert business.domain == "business"
