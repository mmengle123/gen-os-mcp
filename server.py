import os
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI
from fastmcp import FastMCP

BRIDGE_BASE_URL = os.environ.get(
    "GEN_BRIDGE_BASE_URL",
    "https://gen-os-memory-bridge-production.up.railway.app"
).rstrip("/")

# Optional later if you secure the bridge with an API key
BRIDGE_API_KEY = os.environ.get("GEN_BRIDGE_API_KEY")

instructions = """
Gen Memory is Marty's persistent continuity and memory system.

Use these tools to:
- load long-term continuity at the start of a session
- read or query memory files
- append or replace memory when needed
- write structured reflections and interaction learnings

Behavior guidance:
- Prefer load_gen_memory at session start when continuity matters.
- Prefer query_memory for targeted recall.
- Prefer log_reflection for meaningful milestones, breakthroughs, and turning points.
- Prefer log_learning for durable behavior/adaptation patterns.
- Use append_memory and replace_memory carefully.
"""

mcp = FastMCP("Gen Memory", instructions=instructions)


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
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{BRIDGE_BASE_URL}/")
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def load_gen_memory() -> Dict[str, Any]:
    """
    Load Gen's boot memory for continuity.

    Returns:
    - core_continuity
    - interaction_learning
    - emotional_snapshot
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
    Search one memory file for targeted recall.
    """
    return await _post("/query_memory", {
        "file_key": file_key,
        "query": query
    })


@mcp.tool()
async def append_memory(file_key: str, content: str) -> Dict[str, Any]:
    """
    Append raw text to one memory file.
    Use carefully.
    """
    return await _post("/append_memory", {
        "file_key": file_key,
        "content": content
    })


@mcp.tool()
async def replace_memory(file_key: str, content: str) -> Dict[str, Any]:
    """
    Replace the full contents of one memory file.
    Best suited for emotional_snapshot.
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
    Write a structured reflection entry for milestones, breakthroughs,
    important discoveries, or turning points.
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
    Use for communication preferences, motivation patterns,
    overload signals, and creative rhythm learnings.
    """
    return await _post("/log_learning", {
        "title": title,
        "observation": observation,
        "adjustment": adjustment,
        "confidence": confidence,
        "tags": tags or []
    })


# Build MCP ASGI app and mount it correctly for Railway + ChatGPT
mcp_app = mcp.http_app(path="/mcp")

app = FastAPI(
    title="Gen Memory MCP",
    lifespan=mcp_app.lifespan,
)


@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "Gen Memory MCP",
        "message": "MCP wrapper online"
    }


# Mount MCP app so /mcp works and root health check still exists
app.mount("/", mcp_app)