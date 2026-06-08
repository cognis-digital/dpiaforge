"""Command-line interface for DPIAFORGE."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

from . import TOOL_NAME, TOOL_VERSION
from .core import assess


def _load(path: Optional[str]) -> Dict[str, Any]:
    if path in (None, "-"):
        data = sys.stdin.read()
    else:
        with open(path, "r", encoding="utf-8") as fh:
            data = fh.read()
    return json.loads(data)


def _print_table(report: Dict[str, Any]) -> None:
    dpia = report["dpia"]
    ai = report["ai_act"]
    risk = report["risk"]
    lines: List[str] = []
    lines.append(f"DPIAFORGE report :: {report['activity']}")
    lines.append("=" * 60)
    lines.append(f"DPIA verdict      : {dpia['verdict']} ({dpia['criteria_met']} WP248 criteria)")
    for m in dpia["matched"]:
        lines.append(f"    - {m['label']}")
    lines.append(f"AI Act tier       : {ai['tier']}")
    for r in ai["reasons"]:
        lines.append(f"    - {r}")
    lines.append(f"Residual risk     : {risk['residual']}/100 [{risk['band']}] "
                 f"(inherent {risk['inherent']} - mitigation {risk['mitigation_reduction']})")
    lines.append(f"Deployable        : {'YES' if report['deployable'] else 'NO'}")
    lines.append("Recommendations:")
    for rec in report["recommendations"]:
        lines.append(f"    * {rec}")
    if ai.get("obligations"):
        lines.append("Obligations:")
        for ob in ai["obligations"]:
            lines.append(f"    * {ob}")
    print("\n".join(lines))


def _emit(report: Dict[str, Any], fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(report, indent=2))
    else:
        _print_table(report)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="DPIA & EU AI Act impact-assessment generator (offline, stdlib-only).",
    )
    parser.add_argument("--version", action="version",
                        version=f"{TOOL_NAME} {TOOL_VERSION}")
    parser.add_argument("--format", choices=("table", "json"), default="table",
                        help="output format (default: table)")
    sub = parser.add_subparsers(dest="command")

    p_assess = sub.add_parser("assess", help="run full DPIA + AI Act assessment on an activity JSON")
    p_assess.add_argument("input", nargs="?", default="-",
                          help="path to activity JSON (default: stdin)")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 2

    if args.command == "assess":
        try:
            activity = _load(args.input)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"error: could not read activity JSON: {exc}", file=sys.stderr)
            return 1
        try:
            report = assess(activity)
        except ValueError as exc:
            print(f"error: invalid activity: {exc}", file=sys.stderr)
            return 1
        _emit(report, args.format)
        # Non-zero exit when the activity is non-deployable (prohibited practice).
        return 0 if report["deployable"] else 3

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
