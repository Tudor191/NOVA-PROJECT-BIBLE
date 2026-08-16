from nova_contracts import RiskLevel


def test_risk_level_is_importable_from_the_top_level_package() -> None:
    assert RiskLevel.LOW.value == "low"


def test_risk_level_matches_bible_part_14s_five_tier_scale_verbatim() -> None:
    assert [member.value for member in RiskLevel] == [
        "negligible",
        "low",
        "moderate",
        "high",
        "critical",
    ]
