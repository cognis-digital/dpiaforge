"""DPIAFORGE - DPIA & EU AI Act impact-assessment generator.

Standard-library-only toolkit that ingests a processing-activity / AI-system
description (JSON) and produces:
  * a GDPR Art.35 DPIA-threshold determination (WP248 9-criteria test),
  * an EU AI Act (Reg. 2024/1689) risk-tier classification,
  * obligation checklists and a residual-risk score.
"""
from .core import (
    assess,
    dpia_threshold,
    classify_ai_act_tier,
    risk_score,
    WP248_CRITERIA,
    PROHIBITED_PRACTICES,
    HIGH_RISK_ANNEX_III,
)

TOOL_NAME = "dpiaforge"
TOOL_VERSION = "1.0.0"

__all__ = [
    "assess",
    "dpia_threshold",
    "classify_ai_act_tier",
    "risk_score",
    "WP248_CRITERIA",
    "PROHIBITED_PRACTICES",
    "HIGH_RISK_ANNEX_III",
    "TOOL_NAME",
    "TOOL_VERSION",
]
