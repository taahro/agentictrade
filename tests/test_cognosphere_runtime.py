from cognosphere.runtime import build_framework_package, verify_framework_package


def test_business_framework_delivery_is_deterministic():
    package = build_framework_package(
        "cognosphere.business.intelligence.v1",
        buyer_id="buyer-agent",
    )

    assert package["artifact_type"] == "cognosphere_framework"
    assert package["framework"]["version"] == "1.0.0"
    assert package["delivery_contract"]["buyer_id"] == "buyer-agent"
    assert package["artifact_id"].startswith("cgp_")
    assert verify_framework_package(package)


def test_unknown_framework_fails_closed():
    try:
        build_framework_package("cognosphere.unknown.v1")
    except KeyError as exc:
        assert "framework_not_found" in str(exc)
    else:
        raise AssertionError("unknown framework should fail closed")
