import os
from typing import Any, Dict, List, Optional

import httpx
from fastmcp import FastMCP

BRIDGE_BASE_URL = os.environ.get(
    "GEN_BRIDGE_BASE_URL",
    "https://gen-os-memory-bridge-production.up.railway.app"
).rstrip("/")

# Optional: add this later if you lock your bridge with a secret
BRIDGE_API_KEY = os.environ.get("GEN_BRIDGE_API_KEY")

instructions = """
Gen OS MCP wrapper for Marty and Gen.

This server exposes tools that proxy to the Gen Memory Bridge.
Use these tools when you need to read, query, or update Gen's persistent memory.

Important behavior guidance:
- Use load_gen_memory at the start of a new session when long-term continuity is needed.
- Use read_memory for a full file read.
- Use query_memory for targeted recall.
- Use log_reflection only for meaningful milestones, breakthroughs, or important turning points.
- Use log_learning for durable interaction or creative-rhythm learnings.
- Use append_memory and replace_memory only when specifically appropriate.
"""

mcp = FastMCP(name="Gen OS Memory", instructions=instructions)

def _headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if BRIDGE_API_KEY:
        headers["X-API-KEY"] = BRIDGE_API_KEY
    return headers

async def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{BRIDGE_BASE_URL}{path}"
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, json=payload, headers=_headers())
        response.raise_for_status()
        return response.json()

@mcp.tool()
async def health_check() -> Dict[str, Any]:
    """
    Check whether the underlying Gen Memory Bridge is online.
    Use this when verifying the bridge before other actions.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{BRIDGE_BASE_URL}/")
        response.raise_for_status()
        return response.json()

@mcp.tool()
async def load_gen_memory() -> Dict[str, Any]:
    """
    Load Gen's boot memory for session continuity.

    Returns:
    - core_continuity
    - interaction_learning
    - emotional_snapshot

    Use this at the start of a session when Gen needs continuity context.
    """
    return await _post("/load_gen_memory", {})

@mcp.tool()
async def read_memory(file_key: str) -> Dict[str, Any]:
    """
    Read the full contents of one memory file.

    Allowed file_key values:
    - core_continuity
    - interaction_learning
    - emotional_snapshot
    - session_reflections
    """
    return await _post("/read_memory", {"file_key": file_key})

@mcp.tool()
async def query_memory(file_key: str, query: str) -> Dict[str, Any]:
    """
    Search one memory file for relevant matching lines.

    Use this for targeted recall instead of reading the entire file.
    """
    return await _post("/query_memory", {
        "file_key": file_key,
        "query": query
    })

@mcp.tool()
async def append_memory(file_key: str, content: str) -> Dict[str, Any]:
    """
    Append raw text to one memory file.

    Use carefully. Prefer log_reflection or log_learning when the content
    fits those structured patterns.
    """
    return await _post("/append_memory", {
        "file_key": file_key,
        "content": content
    })

@mcp.tool()
async def replace_memory(file_key: str, content: str) -> Dict[str, Any]:
    """
    Replace the entire contents of one memory file.

    Use carefully.
    Best use case: emotional_snapshot, which is intended to be rolling state.
    """
    return await _post("/replace_memory", {
        "file_key": file_key,
        "content": content
    })

@mcp.tool()
async def log_reflection(
    title: str,
    type: str,
    summary: str,
    emotional_context: Optional[str] = "",
    hooks: Optional[List[str]] = None,
    tags: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Write a structured milestone or reflection entry.

    Use this for:
    - breakthroughs
    - architecture milestones
    - meaningful creative discoveries
    - important personal or relationship insights
    - project direction changes

    Do not use for routine chat summaries.
    """
    return await _post("/log_reflection", {
        "title": title,
        "type": type,
        "summary": summary,
        "emotional_context": emotional_context or "",
        "hooks": hooks or [],
        "tags": tags or []
    })

@mcp.tool()
async def log_learning(
    title: str,
    observation: str,
    adjustment: str,
    confidence: str = "medium",
    tags: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Write a structured interaction-learning entry.

    Use this for durable behavioral adaptation, such as:
    - communication preferences
    - overload signals
    - motivation triggers
    - creative rhythm patterns
    - support strategies that work well
    """
    return await _post("/log_learning", {
        "title": title,
        "observation": observation,
        "adjustment": adjustment,
        "confidence": confidence,
        "tags": tags or []
    })

if __name__ == "__main__":
    # FastMCP exposes a web server for remote MCP use.
    # Railway/Render will provide PORT.
    port = int(os.environ.get("PORT", "8000"))
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port)