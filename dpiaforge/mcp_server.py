"""DPIAFORGE MCP server — exposes scan() as an MCP tool for Cognis.Studio."""
from __future__ import annotations
from dpiaforge.core import scan, to_json

def serve() -> int:
    """Start an MCP stdio server. Requires the optional 'mcp' extra:
        pip install "cognis-dpiaforge[mcp]"
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception:
        print("Install the MCP extra: pip install 'cognis-dpiaforge[mcp]'")
        return 1
    app = FastMCP("dpiaforge")

    @app.tool()
    def dpiaforge_scan(target: str) -> str:
        """DPIA and EU AI Act impact-assessment generator. Returns JSON findings."""
        return to_json(scan(target))

    app.run()
    return 0
