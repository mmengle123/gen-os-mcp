import json
import os
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, List, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from fastmcp import FastMCP


MEMORY_FILES = {
    "core_continuity": "1uVuKRShtfPggZY6kUsBdbHQFV-LGcMn3YNIVqP9Xr-Q",
    "interaction_learning": "1X5OCYdGv6_SesSi2TV-9jkuiR8k2dnkwHvhStJ2Ysug",
    "emotional_snapshot": "16sqeAH6wtCFbxCuVyBSbml--wiM0JLDwx4VSUSSh8Y8",
    "session_reflections": "19tO7KNlE6okqaVFSdS2bNpcbiSO82LKQSZs-_L34bUA",
    "cognitive_tuning": "1kQOUwunjXBN4nCy1fJWCm-O6a8Zpzjjg1mzWCrs71vQ",
}

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
]

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


def _normalize_private_key(data: Dict[str, Any]) -> Dict[str, Any]:
    fixed = dict(data)
    if fixed.get("private_key"):
        fixed["private_key"] = fixed["private_key"].replace("\\n", "\n")
    return fixed


@lru_cache(maxsize=1)
def _get_credentials():
    raw_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")

    if raw_json:
        info = _normalize_private_key(json.loads(raw_json))
        return service_account.Credentials.from_service_account_info(
            info,
            scopes=SCOPES,
        )

    keyfile = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "service-account.json")
    return service_account.Credentials.from_service_account_file(
        keyfile,
        scopes=SCOPES,
    )


@lru_cache(maxsize=1)
def _get_drive():
    return build("drive", "v3", credentials=_get_credentials(), cache_discovery=False)


def _today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def _clean_array(value: Optional[List[str]]) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _get_file_id(file_key: str) -> str:
    file_id = MEMORY_FILES.get(file_key)
    if not file_id:
        raise ValueError(f"Invalid file_key: {file_key}")
    return file_id


def export_doc_text(file_key: str) -> str:
    file_id = _get_file_id(file_key)
    drive = _get_drive()

    response = drive.files().export(
        fileId=file_id,
        mimeType="text/plain",
    ).execute()

    if isinstance(response, bytes):
        return response.decode("utf-8")
    if isinstance(response, str):
        return response
    return str(response or "")


def replace_doc_text(file_key: str, content: str) -> None:
    file_id = _get_file_id(file_key)
    drive = _get_drive()

    media = content.encode("utf-8")

    drive.files().update(
        fileId=file_id,
        media_body=None,
        body={},
    ).execute()

    # Upload plain text content back into the Google Doc.
    # This mirrors the behavior of your old Node bridge.
    from googleapiclient.http import MediaIoBaseUpload
    import io

    stream = io.BytesIO(media)
    media_upload = MediaIoBaseUpload(stream, mimetype="text/plain", resumable=False)

    drive.files().update(
        fileId=file_id,
        media_body=media_upload,
    ).execute()


def append_doc_text(file_key: str, content: str) -> None:
    existing = export_doc_text(file_key)
    updated = f"{existing.rstrip()}\n\n{content}" if existing.strip() else content
    replace_doc_text(file_key, updated)


@mcp.tool()
def health_check() -> Dict[str, Any]:
    """
    Check whether the Gen Memory service is online.
    """
    creds = _get_credentials()
    return {
        "status": "ok",
        "message": "Gen Memory service running",
        "has_service_account": bool(creds),
        "memory_files_configured": sorted(MEMORY_FILES.keys()),
    }


@mcp.tool()
def load_gen_memory() -> Dict[str, Any]:
    """
    Load Gen's boot memory for continuity.

    Returns:
    - core_continuity
    - interaction_learning
    - emotional_snapshot
    - cognitive_tuning
    """
    memory = {}
    for key in [
        "core_continuity",
        "interaction_learning",
        "emotional_snapshot",
        "cognitive_tuning",
    ]:
        memory[key] = export_doc_text(key)

    return {
        "status": "memory_loaded",
        "memory": memory,
    }


@mcp.tool()
def read_memory(file_key: str) -> Dict[str, Any]:
    """
    Read the full contents of one memory file.

    Allowed file_key values:
    - core_continuity
    - interaction_learning
    - emotional_snapshot
    - session_reflections
    - cognitive_tuning
    """
    content = export_doc_text(file_key)
    return {
        "status": "ok",
        "file_key": file_key,
        "content": content,
    }


@mcp.tool()
def query_memory(file_key: str, query: str) -> Dict[str, Any]:
    """
    Search one memory file for targeted recall.
    """
    if not query or not isinstance(query, str):
        raise ValueError("query must be a non-empty string")

    text = export_doc_text(file_key)
    matches = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and query.lower() in line.lower()
    ][:20]

    return {
        "status": "query_complete",
        "file_key": file_key,
        "query": query,
        "matches": matches,
    }


@mcp.tool()
def append_memory(file_key: str, content: str) -> Dict[str, Any]:
    """
    Append raw text to one memory file.
    Use carefully.
    """
    if not isinstance(content, str):
        raise ValueError("content must be a string")

    append_doc_text(file_key, content)
    return {
        "status": "memory_appended",
        "file_key": file_key,
    }


@mcp.tool()
def replace_memory(file_key: str, content: str) -> Dict[str, Any]:
    """
    Replace the full contents of one memory file.
    Best suited for emotional_snapshot.
    """
    if not isinstance(content, str):
        raise ValueError("content must be a string")

    replace_doc_text(file_key, content)
    return {
        "status": "memory_replaced",
        "file_key": file_key,
    }


@mcp.tool()
def log_reflection(
    type: str,
    summary: str,
    title: Optional[str] = None,
    emotional_context: Optional[str] = "",
    hooks: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Write a structured reflection entry for milestones, breakthroughs,
    important discoveries, or turning points.
    """
    if not type or not summary:
        raise ValueError("type and summary are required")

    entry_title = title or f"{type.title()} Reflection"
    hook_lines = "\n".join(f"- {h}" for h in _clean_array(hooks))
    tag_line = ", ".join(_clean_array(tags))

    entry = f"""---
[{_today()}] Entry Title: {entry_title}
Type: {type}

Summary:
{summary}

Emotional Context:
{emotional_context or "None provided"}

Continuity Hooks:
{hook_lines or "- None provided"}

Tags:
{tag_line or "none"}

Source:
Gen Memory MCP
---"""

    append_doc_text("session_reflections", entry)

    return {
        "status": "reflection_logged",
        "entry": entry,
    }


@mcp.tool()
def log_learning(
    title: str,
    observation: str,
    adjustment: str,
    confidence: str = "medium",
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Write a structured interaction-learning entry.
    Use for communication preferences, motivation patterns,
    overload signals, and creative rhythm learnings.
    """
    if not title or not observation or not adjustment:
        raise ValueError("title, observation, and adjustment are required")

    tag_line = ", ".join(_clean_array(tags))

    entry = f"""---
[{_today()}] Entry Title: {title}
Type: Interaction Learning

Observation:
{observation}

Adjustment:
{adjustment}

Confidence:
{confidence}

Tags:
{tag_line or "none"}

Source:
Gen Memory MCP
---"""

    append_doc_text("interaction_learning", entry)

    return {
        "status": "learning_logged",
        "entry": entry,
    }


# Export the MCP ASGI app directly.
# This is the app Railway should run with uvicorn.
app = mcp.http_app()