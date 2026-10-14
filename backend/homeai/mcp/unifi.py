from fastmcp import FastMCP
from ..db import initialize, recent_events
mcp = FastMCP("unifi-events-readonly")

@mcp.tool
async def get_security_events(limit: int = 15) -> list[dict]:
    """Read stored UniFi Protect webhook alarms; no raw video is shared."""
    initialize()
    return [e.model_dump(mode="json") for e in recent_events(limit)]

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8103)
