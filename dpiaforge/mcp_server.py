"""DPIAFORGE MCP server — exposes assess() as an MCP tool for Cognis.Studio."""
from __future__ import annotations

import json
import sys

from dpiaforge.core import assess


def serve() -> int:
    """Start an MCP stdio server. Requires the optional 'mcp' extra:
        pip install "cognis-dpiaforge[mcp]"
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception:
        print("Install the MCP extra: pip install 'cognis-dpiaforge[mcp]'", file=sys.stderr)
        return 1
    app = FastMCP("dpiaforge")

    @app.tool()
    def dpiaforge_assess(activity_json: str) -> str:
        """DPIA and EU AI Act impact-assessment generator.

        Args:
            activity_json: JSON string describing the processing activity.

        Returns:
            JSON string with DPIA + AI Act findings.
        """
        try:
            activity = json.loads(activity_json)
        except (json.JSONDecodeError, TypeError) as exc:
            return json.dumps({"error": f"invalid JSON input: {exc}"})
        try:
            report = assess(activity)
        except ValueError as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(report, indent=2)

    app.run()
    return 0
