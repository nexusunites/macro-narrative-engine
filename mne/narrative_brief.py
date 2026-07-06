from dataclasses import dataclass
from datetime import datetime, timezone
import re


SECTION_ORDER = (
    "dominant_story",
    "why_it_changed",
    "market_agreement",
    "attention",
    "overall_assessment",
)

SECTION_LABELS = {
    "dominant_story": "Dominant Story",
    "why_it_changed": "Why It Changed",
    "market_agreement": "Market Agreement",
    "attention": "Attention",
    "overall_assessment": "Overall Assessment",
}

STYLE_GUIDE_ID = "narrative_style_guide.v1"
STYLE_GUIDE_DOC = "docs/narrative_style_guide.md"
FORBIDDEN_TEMPLATE_TERMS = (
    "exploded",
    "collapsed",
    "massive",
    "incredible",
    "shocking",
    "obvious",
    "guaranteed",
    "certain",
    "proves",
    "definitely",
    "must",
    "will",
    "likely",
    "expect",
    "about to",
)


@dataclass(frozen=True)
class EvidenceRef:
    source_module: str
    field_path: str


@dataclass(frozen=True)
class BriefTemplate:
    template_id: str
    section: str
    priority: int
    pattern: str
    required_evidence: tuple[EvidenceRef, ...]
    trigger: str
    exclusivity_group: str | None = None
    confidence: str = "HIGH"
    fallback: bool = False
    allow_empty_text: bool = False
    style_guide: str = STYLE_GUIDE_ID


def _state(source, fallback=None):
    if isinstance(source, dict):
        return source.get("state") or source.get("risk") or fallback
    return fallback


def _safe_number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _format_pct(value):
    number = _safe_number(value, None)
    if number is None:
        return "Unavailable"
    if number > 1:
        number = number / 100
    return f"{number * 100:.1f}%"


def _format_score(value):
    number = _safe_number(value, None)
    if number is None:
        return "Unavailable"
    if number.is_integer():
        return str(int(number))
    return str(round(number, 1))


def _display(value):
    if value is None or value == "":
        return "Unavailable"
    return str(value).replace("_", " ").replace("-", " ").title()


def _get_path(source, path):
    current = source
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current


def _resolve_path(path, bindings):
    resolved = path
    for key, value in bindings.items():
        resolved = resolved.replace("{" + key + "}", str(value))
    return resolved


def _normalize_rotation(rotation):
    if isinstance(rotation, dict) and isinstance(rotation.get("groups"), dict):
        return rotation
    groups = {}
    if isinstance(rotation, list):
        for item in rotation:
            if isinstance(item, dict) and item.get("group"):
                groups[str(item["group"])] = item
    return {"groups": groups}


def _sorted_scores(scores):
    if not isinstance(scores, dict):
        return []
    return sorted(scores.items(), key=lambda item: _safe_number(item[1]), reverse=True)


def _first_change(change_summary):
    if not isinstance(change_summary, dict):
        return None
    changes = change_summary.get("changes")
    if not isinstance(changes, dict):
        return None
    for category in ("major", "narratives", "market", "catalysts"):
        items = changes.get(category)
        if isinstance(items, list) and items:
            item = items[0]
            if isinstance(item, dict):
                return item.get("text")
            return str(item)
    return None


def _has_change_summary(run):
    summary = run.get("change_summary")
    return isinstance(summary, dict)


def _has_required(run, names):
    return all(run.get(name) is not None for name in names)


def _bindings(run):
    groups = _sorted_scores(run.get("group_scores"))
    themes = _sorted_scores(run.get("theme_scores") or run.get("theme_counts"))
    dominant_group = run.get("dominant_group") or (groups[0][0] if groups else None)
    dominant_theme = run.get("dominant_theme") or (themes[0][0] if themes else None)
    challenger_group = groups[1][0] if len(groups) > 1 else None
    rotation = _normalize_rotation(run.get("leadership_rotation"))
    dominant_rotation = _get_path(rotation, f"groups.{dominant_group}.rotation_state") if dominant_group else None
    challenger_rotation = _get_path(rotation, f"groups.{challenger_group}.rotation_state") if challenger_group else None
    pulse = run.get("narrative_pulse") if isinstance(run.get("narrative_pulse"), dict) else {}
    dominant_pulse = pulse.get(dominant_group) if isinstance(pulse.get(dominant_group), dict) else {}
    dynamics = run.get("narrative_dynamics") if isinstance(run.get("narrative_dynamics"), dict) else {}
    crowding = dynamics.get("narrative_crowding") if isinstance(dynamics.get("narrative_crowding"), dict) else {}
    catalyst = run.get("catalyst_environment") if isinstance(run.get("catalyst_environment"), dict) else {}
    positioning = run.get("positioning_environment") if isinstance(run.get("positioning_environment"), dict) else {}
    relationship = run.get("narrative_market_relationship") if isinstance(run.get("narrative_market_relationship"), dict) else {}
    breadth = run.get("breadth_confirmation") if isinstance(run.get("breadth_confirmation"), dict) else {}
    regime = run.get("regime_alignment") if isinstance(run.get("regime_alignment"), dict) else {}
    event_lifecycle = run.get("event_lifecycle") if isinstance(run.get("event_lifecycle"), dict) else {}
    current_event = event_lifecycle.get("current_event") if isinstance(event_lifecycle.get("current_event"), dict) else {}
    first_change = _first_change(run.get("change_summary"))

    return {
        "dominant_group": dominant_group,
        "dominant_group_path": dominant_group,
        "dominant_theme": _display(dominant_theme),
        "dominant_share": _format_pct(run.get("dominant_share")),
        "concentration_gap": _format_score(run.get("concentration_gap")),
        "challenger_group": challenger_group,
        "challenger_group_path": challenger_group,
        "dominant_rotation": dominant_rotation,
        "challenger_rotation": challenger_rotation,
        "dominant_pulse_state": dominant_pulse.get("pulse_state") or "Unavailable",
        "change_text": first_change,
        "relationship_state": _state(relationship, "Unavailable"),
        "breadth_state": _state(breadth, "Unavailable"),
        "regime_state": _state(regime, "Unavailable"),
        "regime_score": _format_score(regime.get("score") if isinstance(regime, dict) else None),
        "crowding_risk": crowding.get("risk") or "Unavailable",
        "catalyst_state": _state(catalyst, "Unavailable"),
        "positioning_state": _state(positioning, "Unavailable"),
        "event_name": current_event.get("event_name") or current_event.get("name"),
    }


def _trigger(template_id, run, bindings):
    required_by_section = {
        "dominant_story": (
            "dominant_theme",
            "dominant_group",
            "theme_scores",
            "group_scores",
            "dominant_share",
            "concentration_gap",
            "narrative_pulse",
            "narrative_leadership",
            "leadership_rotation",
        ),
        "why_it_changed": ("change_summary",),
        "market_agreement": ("breadth_confirmation", "narrative_market_relationship"),
        "overall_assessment": ("regime_alignment",),
    }

    if template_id.startswith("dominant_story.fallback"):
        return not _has_required(run, required_by_section["dominant_story"])
    if template_id.startswith("why_it_changed.fallback"):
        return not _has_required(run, required_by_section["why_it_changed"])
    if template_id.startswith("market_agreement.fallback"):
        return not _has_required(run, required_by_section["market_agreement"])
    if template_id.startswith("overall_assessment.fallback"):
        return not _has_required(run, required_by_section["overall_assessment"])

    if template_id == "dominant_story.contested":
        return (
            _has_required(run, required_by_section["dominant_story"])
            and bindings["challenger_group"]
            and (
                bindings["challenger_rotation"] == "Challenging"
                or bindings["dominant_rotation"] == "Challenged"
            )
        )
    if template_id == "dominant_story.stable":
        return (
            _has_required(run, required_by_section["dominant_story"])
            and not (
                bindings["challenger_group"]
                and (
                    bindings["challenger_rotation"] == "Challenging"
                    or bindings["dominant_rotation"] == "Challenged"
                )
            )
        )
    if template_id == "why_it_changed.changed":
        return _has_change_summary(run) and bool(bindings["change_text"])
    if template_id == "why_it_changed.unchanged":
        return _has_change_summary(run)
    if template_id == "market_agreement.divergence":
        return (
            _has_required(run, required_by_section["market_agreement"])
            and bindings["relationship_state"]
            in {"Narrative Divergence", "Narrative Exhaustion"}
        )
    if template_id == "market_agreement.confirmation":
        return (
            _has_required(run, required_by_section["market_agreement"])
            and (
                bindings["relationship_state"] == "Narrative Confirmation"
                or bindings["breadth_state"] == "Strong Breadth Confirmation"
            )
        )
    if template_id == "market_agreement.mixed":
        return (
            _has_required(run, required_by_section["market_agreement"])
            and bindings["relationship_state"]
            not in {
                "Narrative Divergence",
                "Narrative Exhaustion",
                "Narrative Confirmation",
            }
            and bindings["breadth_state"] != "Strong Breadth Confirmation"
        )
    if template_id == "attention.crowding":
        return bindings["crowding_risk"] in {"HIGH", "MODERATE"}
    if template_id == "attention.catalyst":
        return bindings["catalyst_state"] not in {
            "Unavailable",
            "No Catalyst Pressure",
            "Low Catalyst Pressure",
            "Quiet Catalyst Environment",
        }
    if template_id == "attention.positioning":
        return bindings["positioning_state"] not in {
            "Unavailable",
            "No Active Positioning",
            "Neutral Positioning",
        }
    if template_id == "attention.none":
        return True
    if template_id == "overall_assessment.regime":
        return _has_required(run, required_by_section["overall_assessment"])
    return False


TEMPLATES = (
    BriefTemplate(
        "dominant_story.contested",
        "dominant_story",
        10,
        "{dominant_group} remains the dominant narrative, but leadership is being challenged by {challenger_group}; dominant share is {dominant_share} and the concentration gap is {concentration_gap}.",
        (
            EvidenceRef("narrative_leadership", "dominant_group"),
            EvidenceRef("group_scores", "{dominant_group_path}"),
            EvidenceRef("group_scores", "{challenger_group_path}"),
            EvidenceRef("dominant_share", ""),
            EvidenceRef("concentration_gap", ""),
            EvidenceRef("leadership_rotation", "groups.{challenger_group_path}.rotation_state"),
        ),
        "challenger rotation is Challenging or dominant rotation is Challenged",
        "dominant_story.leadership",
    ),
    BriefTemplate(
        "dominant_story.stable",
        "dominant_story",
        20,
        "{dominant_group} remains the dominant narrative, led by {dominant_theme}; dominant share is {dominant_share}, the concentration gap is {concentration_gap}, and pulse is {dominant_pulse_state}.",
        (
            EvidenceRef("dominant_group", ""),
            EvidenceRef("dominant_theme", ""),
            EvidenceRef("dominant_share", ""),
            EvidenceRef("concentration_gap", ""),
            EvidenceRef("narrative_pulse", "{dominant_group_path}.pulse_state"),
            EvidenceRef("narrative_leadership", "dominant_group"),
        ),
        "dominant narrative inputs are present",
        "dominant_story.leadership",
    ),
    BriefTemplate(
        "dominant_story.fallback",
        "dominant_story",
        99,
        "Dominant narrative data is unavailable for this run.",
        (EvidenceRef("dominant_group", ""),),
        "one or more required dominant story inputs are missing",
        "dominant_story.leadership",
        "LOW",
        True,
    ),
    BriefTemplate(
        "why_it_changed.changed",
        "why_it_changed",
        10,
        "The primary change since the prior run is: {change_text}",
        (EvidenceRef("change_summary", "changes"),),
        "change_summary contains at least one material change",
    ),
    BriefTemplate(
        "why_it_changed.unchanged",
        "why_it_changed",
        20,
        "Narrative conditions are largely unchanged from the prior run.",
        (EvidenceRef("change_summary", "has_changes"),),
        "change_summary is present without material changes",
        confidence="MEDIUM",
        fallback=True,
    ),
    BriefTemplate(
        "why_it_changed.fallback",
        "why_it_changed",
        99,
        "Change summary data is unavailable for this run.",
        (EvidenceRef("change_summary", ""),),
        "change_summary is missing",
        confidence="LOW",
        fallback=True,
    ),
    BriefTemplate(
        "market_agreement.divergence",
        "market_agreement",
        10,
        "Market confirmation has diverged: the narrative and market relationship is {relationship_state}, while breadth is {breadth_state}.",
        (
            EvidenceRef("narrative_market_relationship", "state"),
            EvidenceRef("breadth_confirmation", "state"),
        ),
        "narrative_market_relationship indicates divergence or exhaustion",
        "market_agreement.state",
    ),
    BriefTemplate(
        "market_agreement.confirmation",
        "market_agreement",
        20,
        "Market confirmation is aligned: the narrative and market relationship is {relationship_state}, and breadth is {breadth_state}.",
        (
            EvidenceRef("narrative_market_relationship", "state"),
            EvidenceRef("breadth_confirmation", "state"),
        ),
        "relationship or breadth indicates confirmation",
        "market_agreement.state",
    ),
    BriefTemplate(
        "market_agreement.mixed",
        "market_agreement",
        30,
        "Market agreement remains mixed: the narrative and market relationship is {relationship_state}, and breadth is {breadth_state}.",
        (
            EvidenceRef("narrative_market_relationship", "state"),
            EvidenceRef("breadth_confirmation", "state"),
        ),
        "market agreement inputs are present without confirmation or divergence",
        "market_agreement.state",
        confidence="MEDIUM",
        fallback=True,
    ),
    BriefTemplate(
        "market_agreement.fallback",
        "market_agreement",
        99,
        "Market agreement data is unavailable for this run.",
        (EvidenceRef("narrative_market_relationship", ""),),
        "market agreement required inputs are missing",
        "market_agreement.state",
        confidence="LOW",
        fallback=True,
    ),
    BriefTemplate(
        "attention.crowding",
        "attention",
        10,
        "Narrative crowding deserves attention because crowding risk is {crowding_risk}.",
        (EvidenceRef("narrative_dynamics", "narrative_crowding.risk"),),
        "crowding risk is HIGH or MODERATE",
    ),
    BriefTemplate(
        "attention.catalyst",
        "attention",
        20,
        "Catalyst conditions deserve attention because the catalyst environment is {catalyst_state}.",
        (EvidenceRef("catalyst_environment", "state"),),
        "catalyst state is active",
    ),
    BriefTemplate(
        "attention.positioning",
        "attention",
        30,
        "Positioning deserves attention because the positioning environment is {positioning_state}.",
        (EvidenceRef("positioning_environment", "state"),),
        "positioning state is active",
    ),
    BriefTemplate(
        "attention.none",
        "attention",
        99,
        "",
        (EvidenceRef("narrative_dynamics", "narrative_crowding.risk"),),
        "no attention condition qualifies",
        allow_empty_text=True,
    ),
    BriefTemplate(
        "overall_assessment.regime",
        "overall_assessment",
        10,
        "Overall the environment is {regime_state}, with a regime alignment score of {regime_score}.",
        (
            EvidenceRef("regime_alignment", "state"),
            EvidenceRef("regime_alignment", "score"),
        ),
        "regime_alignment is present",
    ),
    BriefTemplate(
        "overall_assessment.fallback",
        "overall_assessment",
        99,
        "Overall assessment data is unavailable for this run.",
        (EvidenceRef("regime_alignment", ""),),
        "regime_alignment is missing",
        confidence="LOW",
        fallback=True,
    ),
)


def validate_template_library(templates=TEMPLATES):
    seen = set()
    for template in templates:
        if template.template_id in seen:
            raise ValueError(f"Duplicate narrative brief template_id: {template.template_id}")
        seen.add(template.template_id)
        if template.style_guide != STYLE_GUIDE_ID:
            raise ValueError(f"{template.template_id} is not bound to {STYLE_GUIDE_ID}")
        if not template.required_evidence:
            raise ValueError(f"{template.template_id} has no required evidence")
        lower_pattern = template.pattern.lower()
        for term in FORBIDDEN_TEMPLATE_TERMS:
            if re.search(rf"(^|\W){re.escape(term)}($|\W)", lower_pattern):
                raise ValueError(
                    f"{template.template_id} violates {STYLE_GUIDE_ID}: {term}"
                )


validate_template_library()


def _eligible(template, run, bindings, sources):
    if not _trigger(template.template_id, run, bindings):
        return False, "trigger condition false"

    for ref in template.required_evidence:
        path = _resolve_path(ref.field_path, bindings)
        if ref.source_module not in sources:
            return False, f"missing source module: {ref.source_module}"
        if template.allow_empty_text:
            continue
        if path and _get_path(sources[ref.source_module], path) is None:
            return False, f"missing evidence: {ref.source_module}.{path}"
    return True, "selected"


def _make_sources(run):
    sources = dict(run)
    sources["leadership_rotation"] = _normalize_rotation(run.get("leadership_rotation"))
    for name in (
        "dominant_theme",
        "dominant_group",
        "theme_scores",
        "group_scores",
        "dominant_share",
        "concentration_gap",
        "narrative_leadership",
        "narrative_pulse",
        "leadership_rotation",
        "narrative_dynamics",
        "narrative_crowding",
        "change_summary",
        "event_lifecycle",
        "catalyst_environment",
        "positioning_environment",
        "market_environment",
        "breadth_confirmation",
        "narrative_market_relationship",
        "regime_alignment",
        "market_expression",
    ):
        sources.setdefault(name, None)
    return sources


def _build_evidence(template, bindings, sources, registry, timestamp):
    evidence_ids = []
    for ref in template.required_evidence:
        path = _resolve_path(ref.field_path, bindings)
        value = _get_path(sources.get(ref.source_module), path) if path else sources.get(ref.source_module)
        key = (ref.source_module, path)
        if key not in registry:
            evidence_id = f"e{len(registry) + 1:03d}"
            registry[key] = {
                "evidence_id": evidence_id,
                "source_module": ref.source_module,
                "field_path": path,
                "value_at_evaluation": value,
                "run_timestamp_utc": timestamp,
            }
        evidence_ids.append(registry[key]["evidence_id"])
    return evidence_ids


def _select_templates(run, bindings, sources):
    selected = []
    diagnostics = {}
    conflict_log = []
    selected_groups = {}

    for section in SECTION_ORDER:
        diagnostics[section] = []
        section_selected = None
        candidates = sorted(
            [template for template in TEMPLATES if template.section == section],
            key=lambda template: template.priority,
        )
        for template in candidates:
            eligible, reason = _eligible(template, run, bindings, sources)
            diagnostics[section].append(
                {
                    "template_id": template.template_id,
                    "eligible": eligible,
                    "reason": reason,
                    "trigger_condition": template.trigger,
                }
            )
            if not eligible:
                continue
            group = template.exclusivity_group
            if section_selected is not None:
                if group and group in selected_groups:
                    conflict_log.append(
                        {
                            "exclusivity_group": group,
                            "kept_template_id": selected_groups[group],
                            "suppressed_template_id": template.template_id,
                        }
                    )
                continue
            if group and group in selected_groups:
                conflict_log.append(
                    {
                        "exclusivity_group": group,
                        "kept_template_id": selected_groups[group],
                        "suppressed_template_id": template.template_id,
                    }
                )
                continue
            if group:
                selected_groups[group] = template.template_id
            section_selected = template
        if section_selected is not None:
            selected.append(section_selected)
    return selected, diagnostics, conflict_log


def _section_confidence(template, run):
    if template.section == "market_agreement" and run.get("positioning_environment") is None:
        return "MEDIUM" if template.confidence == "HIGH" else template.confidence
    if (
        template.section == "attention"
        and any(
            run.get(field) is None
            for field in ("narrative_dynamics", "catalyst_environment", "positioning_environment")
        )
    ):
        return "MEDIUM" if template.confidence == "HIGH" else template.confidence
    return template.confidence


def _confidence(sections, conflict_log):
    if any(section["section_confidence"] == "LOW" for section in sections):
        return "LOW"
    if len(conflict_log) > 1:
        return "LOW"
    if conflict_log:
        return "MEDIUM"
    if any(section["section_confidence"] == "MEDIUM" for section in sections):
        return "MEDIUM"
    return "HIGH"


def _limitations(run, sections, conflict_log):
    notes = []
    required_fields = {
        "dominant_story": (
            "dominant_theme",
            "dominant_group",
            "theme_scores",
            "group_scores",
            "dominant_share",
            "concentration_gap",
            "narrative_pulse",
            "narrative_leadership",
            "leadership_rotation",
        ),
        "why_it_changed": ("change_summary",),
        "market_agreement": ("breadth_confirmation", "narrative_market_relationship"),
        "overall_assessment": ("regime_alignment",),
    }
    for section, fields in required_fields.items():
        missing = [field for field in fields if run.get(field) is None]
        if missing:
            notes.append(
                f"{SECTION_LABELS[section]} used unavailable-data handling because missing inputs were: {', '.join(missing)}."
            )
    optional_fields = (
        "narrative_dynamics",
        "catalyst_environment",
        "positioning_environment",
        "market_environment",
        "event_lifecycle",
        "market_expression",
    )
    for field in optional_fields:
        if run.get(field) is None:
            notes.append(f"{_display(field)} data was unavailable for this run.")
    if any(section["fallback_used"] for section in sections):
        notes.append("One or more sections used a fallback or low-specificity template.")
    if conflict_log:
        notes.append("One or more mutually exclusive templates were suppressed.")
    return notes


def _key_points(sections, evidence_registry):
    evidence_by_id = {item["evidence_id"]: item for item in evidence_registry}
    points = []
    for section in sections:
        if not section["text"]:
            continue
        modules = []
        for evidence_id in section["evidence"]:
            evidence = evidence_by_id.get(evidence_id)
            if evidence and evidence["source_module"] not in modules:
                modules.append(evidence["source_module"])
        points.append(f"{SECTION_LABELS[section['section']]}: supported by {', '.join(modules)}.")
    return points


def generate_narrative_brief(run, run_timestamp_utc=None):
    timestamp = run_timestamp_utc or datetime.now(timezone.utc).isoformat()
    bindings = _bindings(run)
    sources = _make_sources(run)
    templates, diagnostics, conflict_log = _select_templates(run, bindings, sources)
    registry = {}
    sections = []

    for template in templates:
        text = template.pattern.format(**bindings) if template.pattern else ""
        evidence = _build_evidence(template, bindings, sources, registry, timestamp)
        section_confidence = _section_confidence(template, run)
        sections.append(
            {
                "section": template.section,
                "template_id": template.template_id,
                "text": text,
                "evidence": evidence,
                "section_confidence": section_confidence,
                "fallback_used": template.fallback or section_confidence != template.confidence,
            }
        )

    evidence_registry = list(registry.values())
    summary = " ".join(section["text"] for section in sections if section["text"])
    headline_section = next(
        (section for section in sections if section["section"] == "dominant_story"),
        None,
    )
    headline = headline_section["text"] if headline_section else "Dominant narrative data is unavailable for this run."
    confidence = _confidence(sections, conflict_log)

    return {
        "run_timestamp_utc": timestamp,
        "headline": headline,
        "summary": summary,
        "sections": sections,
        "key_points": _key_points(sections, evidence_registry),
        "evidence_registry": evidence_registry,
        "confidence": confidence,
        "limitations": _limitations(run, sections, conflict_log),
        "diagnostics": {
            "style_guide": STYLE_GUIDE_ID,
            "style_guide_doc": STYLE_GUIDE_DOC,
            "template_evaluations": diagnostics,
            "conflict_log": conflict_log,
        },
    }
