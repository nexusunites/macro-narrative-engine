from copy import deepcopy

from mne.narrative_brief import generate_narrative_brief


def base_run():
    return {
        "timestamp": "2026-07-02_090000",
        "dominant_theme": "ai",
        "dominant_group": "AI / Tech Growth",
        "theme_scores": {"ai": 15, "inflation": 8},
        "group_scores": {"AI / Tech Growth": 30, "Macro Pressure": 26},
        "dominant_share": 0.54,
        "concentration_gap": 4,
        "narrative_pulse": {
            "AI / Tech Growth": {
                "pulse_state": "Strong",
                "confidence": "High",
            }
        },
        "narrative_leadership": {
            "dominant_group": "AI / Tech Growth",
            "dominant_group_runs": 4,
            "leaders": [
                {"rank": 1, "group": "AI / Tech Growth", "score": 30},
                {"rank": 2, "group": "Macro Pressure", "score": 26},
            ],
        },
        "leadership_rotation": [
            {
                "group": "AI / Tech Growth",
                "rotation_state": "Challenged",
                "share_delta": -1.0,
                "rotation_streak": 4,
                "reason": "AI / Tech Growth is Challenged.",
            },
            {
                "group": "Macro Pressure",
                "rotation_state": "Challenging",
                "share_delta": 3.5,
                "rotation_streak": 2,
                "reason": "Macro Pressure is Challenging.",
            },
        ],
        "narrative_dynamics": {
            "narrative_crowding": {
                "risk": "HIGH",
                "reason": "AI / Tech Growth remains dominant.",
            }
        },
        "change_summary": {
            "compared_with": "2026-07-01 09:00",
            "has_changes": True,
            "changes": {
                "major": [],
                "narratives": [
                    {
                        "text": "Macro Pressure strengthened: 21 -> 26.",
                        "importance": 5,
                    }
                ],
                "market": [],
                "catalysts": [],
            },
        },
        "event_lifecycle": {
            "current_event": {
                "event_name": "CPI",
                "lifecycle_state": "POST_RELEASE_DIGESTION",
            }
        },
        "catalyst_environment": {
            "state": "Active Catalyst Positioning",
            "confidence": "Moderate",
        },
        "positioning_environment": {
            "state": "Pre-Catalyst Positioning",
            "confidence": "Moderate",
        },
        "market_environment": {
            "state": "Low-Conviction Chop",
            "confidence": "Moderate",
        },
        "breadth_confirmation": {
            "state": "Weak Breadth",
            "confidence": "Moderate",
        },
        "narrative_market_relationship": {
            "state": "Narrative Divergence",
            "confidence": "High",
        },
        "regime_alignment": {
            "state": "Conflicted Environment",
            "score": 35,
            "confidence": "High",
        },
        "market_expression": {
            "mapped": True,
            "primary": ["QQQ", "SMH"],
        },
    }


def section(brief, name):
    return next(item for item in brief["sections"] if item["section"] == name)


def test_full_brief_is_deterministic_and_evidence_backed():
    run = base_run()
    first = generate_narrative_brief(run, "2026-07-02T13:00:00+00:00")
    second = generate_narrative_brief(deepcopy(run), "2026-07-02T13:00:00+00:00")

    assert first == second
    assert first["confidence"] == "HIGH"
    assert [item["section"] for item in first["sections"]] == [
        "dominant_story",
        "why_it_changed",
        "market_agreement",
        "attention",
        "overall_assessment",
    ]
    assert section(first, "dominant_story")["template_id"] == "dominant_story.contested"
    assert section(first, "market_agreement")["template_id"] == "market_agreement.divergence"
    assert first["diagnostics"]["conflict_log"] == []

    registry_ids = {item["evidence_id"] for item in first["evidence_registry"]}
    for brief_section in first["sections"]:
        if brief_section["text"]:
            assert brief_section["evidence"]
            assert set(brief_section["evidence"]).issubset(registry_ids)


def test_missing_optional_positioning_lowers_market_agreement_completeness():
    run = base_run()
    run.pop("positioning_environment")
    brief = generate_narrative_brief(run, "2026-07-02T13:00:00+00:00")

    market = section(brief, "market_agreement")
    assert market["template_id"] == "market_agreement.divergence"
    assert market["section_confidence"] == "MEDIUM"
    assert brief["confidence"] == "MEDIUM"
    assert any("Positioning Environment" in note for note in brief["limitations"])


def test_missing_required_regime_uses_hard_fallback_and_low_confidence():
    run = base_run()
    run.pop("regime_alignment")
    brief = generate_narrative_brief(run, "2026-07-02T13:00:00+00:00")

    overall = section(brief, "overall_assessment")
    assert overall["template_id"] == "overall_assessment.fallback"
    assert overall["section_confidence"] == "LOW"
    assert overall["fallback_used"] is True
    assert brief["confidence"] == "LOW"


def test_no_material_change_uses_unchanged_template():
    run = base_run()
    run["change_summary"] = {
        "compared_with": "2026-07-01 09:00",
        "has_changes": False,
        "changes": {"major": [], "narratives": [], "market": [], "catalysts": []},
    }
    brief = generate_narrative_brief(run, "2026-07-02T13:00:00+00:00")

    changed = section(brief, "why_it_changed")
    assert changed["template_id"] == "why_it_changed.unchanged"
    assert "largely unchanged" in changed["text"]


def test_empty_attention_section_is_schema_valid_when_nothing_qualifies():
    run = base_run()
    run["narrative_dynamics"]["narrative_crowding"]["risk"] = "LOW"
    run["catalyst_environment"]["state"] = "No Catalyst Pressure"
    run["positioning_environment"]["state"] = "Neutral Positioning"
    brief = generate_narrative_brief(run, "2026-07-02T13:00:00+00:00")

    attention = section(brief, "attention")
    assert attention["template_id"] == "attention.none"
    assert attention["text"] == ""
    assert "attention" not in brief["summary"].lower()
