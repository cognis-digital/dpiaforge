"""Core assessment engine for DPIAFORGE.

References:
  * GDPR Art. 35 + WP248 rev.01 (criteria for "likely high risk").
  * EU AI Act (Regulation (EU) 2024/1689): Art. 5 (prohibited),
    Art. 6 + Annex III (high-risk), Art. 50 (transparency), Art. 95 (minimal).

All logic is deterministic and offline. Input is a plain dict describing a
processing activity / AI system.
"""
from __future__ import annotations

from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# WP248 rev.01 - the nine criteria. Two or more => DPIA strongly advised.
# Each entry maps a criterion key to (label, list-of-input-flags-that-trigger).
# ---------------------------------------------------------------------------
WP248_CRITERIA: Dict[str, str] = {
    "evaluation_scoring": "Evaluation or scoring (incl. profiling/predicting)",
    "automated_decision": "Automated decision-making with legal/significant effect",
    "systematic_monitoring": "Systematic monitoring of a publicly accessible area",
    "sensitive_data": "Sensitive data or data of a highly personal nature",
    "large_scale": "Data processed on a large scale",
    "matching_combining": "Matching or combining datasets",
    "vulnerable_subjects": "Data concerning vulnerable data subjects",
    "novel_technology": "Innovative use or new technological/organisational solution",
    "prevents_rights": "Processing prevents subjects exercising a right / using a service",
}

# EU AI Act Art. 5 - prohibited practices (input flag -> citation/label).
PROHIBITED_PRACTICES: Dict[str, str] = {
    "subliminal_manipulation": "Art.5(1)(a) subliminal/manipulative techniques causing harm",
    "exploits_vulnerabilities": "Art.5(1)(b) exploiting age/disability/social vulnerability",
    "social_scoring": "Art.5(1)(c) social scoring by/for public authorities",
    "predictive_policing_profiling": "Art.5(1)(d) crime-risk prediction solely from profiling",
    "untargeted_facial_scraping": "Art.5(1)(e) untargeted scraping of facial images",
    "emotion_inference_work_edu": "Art.5(1)(f) emotion inference in workplace/education",
    "biometric_categorisation_sensitive": "Art.5(1)(g) biometric categorisation of sensitive traits",
    "realtime_remote_biometric_public": "Art.5(1)(h) real-time remote biometric ID in public (LE)",
}

# EU AI Act Annex III high-risk use-case areas (input flag -> citation/label).
HIGH_RISK_ANNEX_III: Dict[str, str] = {
    "biometrics": "Annex III(1) remote biometric identification / categorisation",
    "critical_infrastructure": "Annex III(2) safety of critical digital/road/utility infrastructure",
    "education": "Annex III(3) access, scoring, proctoring in education",
    "employment": "Annex III(4) recruitment, task allocation, monitoring of workers",
    "essential_services": "Annex III(5) access to public benefits, credit scoring, insurance",
    "law_enforcement": "Annex III(6) law-enforcement risk assessment / evidence eval",
    "migration_border": "Annex III(7) migration, asylum, border control",
    "justice_democracy": "Annex III(8) administration of justice / democratic processes",
}

_ROLE_OBLIGATIONS = {
    "provider": [
        "Establish a risk-management system (Art.9)",
        "Data governance & quality of training/validation/test sets (Art.10)",
        "Draw up technical documentation (Art.11 / Annex IV)",
        "Automatic event logging / traceability (Art.12)",
        "Ensure transparency & instructions for use (Art.13)",
        "Design for human oversight (Art.14)",
        "Accuracy, robustness & cybersecurity (Art.15)",
        "Conformity assessment + EU declaration + CE marking (Art.43/47/48)",
        "Register in the EU database before placing on market (Art.49)",
    ],
    "deployer": [
        "Use system per instructions; assign competent human oversight (Art.26)",
        "Ensure input data is relevant & representative for intended purpose (Art.26)",
        "Monitor operation & suspend + inform provider on serious risk (Art.26/72)",
        "Keep automatically generated logs (Art.26)",
        "Conduct a Fundamental Rights Impact Assessment where required (Art.27)",
        "Inform affected persons of high-risk AI decisions (Art.26)",
    ],
}


def _truthy(value: Any) -> bool:
    return bool(value) and value not in ("false", "no", "0", 0)


def _flags(activity: Dict[str, Any]) -> Dict[str, bool]:
    """Normalise the input's flag dict (case/spacing-insensitive keys)."""
    raw = activity.get("flags", {})
    if not isinstance(raw, dict):
        raw = {}
    out = {}
    for k, v in raw.items():
        out[str(k).strip().lower()] = _truthy(v)
    return out


def dpia_threshold(activity: Dict[str, Any]) -> Dict[str, Any]:
    """Apply the WP248 nine-criteria test (GDPR Art.35)."""
    flags = _flags(activity)
    matched = [
        {"criterion": key, "label": WP248_CRITERIA[key]}
        for key in WP248_CRITERIA
        if flags.get(key)
    ]
    count = len(matched)
    if count >= 2:
        verdict, required = "DPIA_REQUIRED", True
    elif count == 1:
        verdict, required = "DPIA_RECOMMENDED", False
    else:
        verdict, required = "DPIA_NOT_INDICATED", False
    return {
        "verdict": verdict,
        "dpia_required": required,
        "criteria_met": count,
        "matched": matched,
        "basis": "GDPR Art.35 + WP248 rev.01 (>=2 criteria => high risk)",
    }


def classify_ai_act_tier(activity: Dict[str, Any]) -> Dict[str, Any]:
    """Classify under EU AI Act risk tiers."""
    flags = _flags(activity)
    is_ai = _truthy(activity.get("is_ai_system", False))

    if not is_ai:
        return {
            "tier": "NOT_AN_AI_SYSTEM",
            "is_ai_system": False,
            "reasons": ["Activity not declared as an AI system; AI Act N/A."],
            "obligations": [],
        }

    prohibited = [
        {"flag": k, "basis": PROHIBITED_PRACTICES[k]}
        for k in PROHIBITED_PRACTICES
        if flags.get(k)
    ]
    if prohibited:
        return {
            "tier": "PROHIBITED",
            "is_ai_system": True,
            "reasons": [p["basis"] for p in prohibited],
            "matched": prohibited,
            "obligations": ["Must not be placed on the market or put into service (Art.5)."],
        }

    annex_iii = [
        {"flag": k, "basis": HIGH_RISK_ANNEX_III[k]}
        for k in HIGH_RISK_ANNEX_III
        if flags.get(k)
    ]
    safety_component = _truthy(activity.get("safety_component", False))
    if annex_iii or safety_component:
        role = str(activity.get("role", "provider")).strip().lower()
        obligations = list(_ROLE_OBLIGATIONS.get(role, _ROLE_OBLIGATIONS["provider"]))
        reasons = [a["basis"] for a in annex_iii]
        if safety_component:
            reasons.append("Art.6(1) safety component of a regulated product (Annex I).")
        return {
            "tier": "HIGH_RISK",
            "is_ai_system": True,
            "role": role,
            "reasons": reasons,
            "matched": annex_iii,
            "obligations": obligations,
        }

    transparency_flags = [
        f for f in ("interacts_with_humans", "generates_synthetic_content",
                    "emotion_recognition", "deepfake")
        if flags.get(f)
    ]
    if transparency_flags:
        return {
            "tier": "LIMITED_RISK",
            "is_ai_system": True,
            "reasons": ["Transparency obligations apply (Art.50): " + ", ".join(transparency_flags)],
            "matched": transparency_flags,
            "obligations": [
                "Inform natural persons they interact with an AI system (Art.50(1)).",
                "Mark synthetic/deepfake content as artificially generated (Art.50(2),(4)).",
            ],
        }

    return {
        "tier": "MINIMAL_RISK",
        "is_ai_system": True,
        "reasons": ["No prohibited/high-risk/transparency triggers; minimal-risk (Art.95 codes voluntary)."],
        "obligations": ["Voluntary codes of conduct encouraged (Art.95)."],
    }


def risk_score(activity: Dict[str, Any], dpia: Dict[str, Any], ai_tier: Dict[str, Any]) -> Dict[str, Any]:
    """Compute a 0-100 residual-risk score from inherent risk minus mitigations."""
    inherent = 0
    inherent += dpia["criteria_met"] * 8  # up to 72
    tier_weight = {
        "PROHIBITED": 100,
        "HIGH_RISK": 40,
        "LIMITED_RISK": 15,
        "MINIMAL_RISK": 5,
        "NOT_AN_AI_SYSTEM": 0,
    }
    inherent += tier_weight.get(ai_tier["tier"], 0)

    raw_subjects = activity.get("data_subjects", 0)
    try:
        subjects = int(raw_subjects) if raw_subjects is not None else 0
        if subjects < 0:
            subjects = 0
    except (ValueError, TypeError):
        subjects = 0
    if subjects >= 1_000_000:
        inherent += 15
    elif subjects >= 100_000:
        inherent += 10
    elif subjects >= 10_000:
        inherent += 5

    inherent = min(inherent, 100)

    measures = activity.get("mitigations", [])
    if not isinstance(measures, (list, tuple)):
        measures = []
    # Each implemented safeguard reduces residual risk (diminishing, capped).
    reduction = min(len(measures) * 7, 60)
    if ai_tier["tier"] == "PROHIBITED":
        reduction = 0  # mitigations cannot cure a prohibited practice

    residual = max(inherent - reduction, 0)
    if residual >= 70 or ai_tier["tier"] == "PROHIBITED":
        band = "CRITICAL"
    elif residual >= 45:
        band = "HIGH"
    elif residual >= 20:
        band = "MEDIUM"
    else:
        band = "LOW"
    return {
        "inherent": inherent,
        "mitigation_reduction": reduction,
        "residual": residual,
        "band": band,
        "mitigations_counted": len(measures),
    }


def _recommendations(dpia, ai_tier, score) -> List[str]:
    recs: List[str] = []
    if ai_tier["tier"] == "PROHIBITED":
        recs.append("STOP: the practice is banned under AI Act Art.5; do not deploy.")
    if dpia["dpia_required"]:
        recs.append("Conduct and document a full DPIA before processing (GDPR Art.35).")
        recs.append("Consult the supervisory authority if residual risk stays high (Art.36).")
    if ai_tier["tier"] == "HIGH_RISK":
        recs.append("Complete conformity assessment & EU-database registration before go-live.")
    if ai_tier["tier"] == "LIMITED_RISK":
        recs.append("Implement Art.50 transparency notices and content marking.")
    if score["band"] in ("HIGH", "CRITICAL") and ai_tier["tier"] != "PROHIBITED":
        recs.append("Residual risk elevated: add technical & organisational safeguards before launch.")
    if not recs:
        recs.append("No blocking issues identified; document the assessment and review periodically.")
    return recs


def assess(activity: Dict[str, Any]) -> Dict[str, Any]:
    """Run the full assessment pipeline and return a structured report.

    Raises:
        ValueError: if *activity* is not a dict or contains structurally invalid values.
    """
    if not isinstance(activity, dict):
        raise ValueError("activity must be a JSON object (dict), got: "
                         f"{type(activity).__name__}")
    if not activity:
        raise ValueError("activity must not be empty — supply at least a 'name' field")
    name_raw = activity.get("name") or activity.get("system_name")
    if name_raw is not None and not isinstance(name_raw, str):
        raise ValueError("'name' must be a string")
    name = str(name_raw).strip() if name_raw else "unnamed activity"

    dpia = dpia_threshold(activity)
    ai_tier = classify_ai_act_tier(activity)
    score = risk_score(activity, dpia, ai_tier)
    recs = _recommendations(dpia, ai_tier, score)

    compliant = not (ai_tier["tier"] == "PROHIBITED")
    return {
        "tool": "dpiaforge",
        "activity": name,
        "dpia": dpia,
        "ai_act": ai_tier,
        "risk": score,
        "recommendations": recs,
        "deployable": compliant,
    }
