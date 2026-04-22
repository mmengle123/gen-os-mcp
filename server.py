import json
import logging
import os
import threading
import time
from collections import defaultdict
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


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
- Prefer end_session_sweep for a full five-log end-of-session write in one server-side call.
- Prefer log_reflection for meaningful milestones, breakthroughs, and turning points.
- Prefer log_learning for durable behavior/adaptation patterns.
- Use append_memory and replace_memory carefully.
"""

mcp = FastMCP("Gen Memory", instructions=instructions)
logger = logging.getLogger("gen_memory")

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

MAX_DOC_WRITE_ATTEMPTS = 4
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
RETRYABLE_400_HINTS = (
    "revision",
    "stale",
    "must be less than",
    "out of bounds",
    "index",
)
_doc_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)


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


@lru_cache(maxsize=1)
def _get_docs():
    return build("docs", "v1", credentials=_get_credentials(), cache_discovery=False)


def _today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def _clean_array(value: Optional[List[str]]) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _normalize_text(text: str) -> str:
    if not isinstance(text, str):
        raise ValueError("content must be a string")
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def _get_file_id(file_key: str) -> str:
    file_id = MEMORY_FILES.get(file_key)
    if not file_id:
        raise ValueError(f"Invalid file_key: {file_key}")
    return file_id


def _get_doc_state(file_key: str) -> Dict[str, Any]:
    file_id = _get_file_id(file_key)
    docs = _get_docs()

    doc = docs.documents().get(
        documentId=file_id,
        fields="body/content/endIndex,revisionId",
    ).execute()

    body = doc.get("body", {}).get("content", [])
    end_index = body[-1].get("endIndex", 1) if body else 1

    return {
        "end_index": end_index,
        "revision_id": doc.get("revisionId"),
    }


def _is_retryable_docs_error(exc: Exception) -> bool:
    if not isinstance(exc, HttpError):
        return False

    status = getattr(exc.resp, "status", None)
    if status in RETRYABLE_STATUS_CODES:
        return True

    if status == 400:
        message = str(exc).lower()
        return any(hint in message for hint in RETRYABLE_400_HINTS)

    return False


def _retry_delay_seconds(attempt: int) -> float:
    return min(0.35 * (2 ** (attempt - 1)), 3.0)


def _run_docs_write(
    file_key: str,
    operation_name: str,
    build_request_body,
) -> Dict[str, Any]:
    file_id = _get_file_id(file_key)

    with _doc_locks[file_key]:
        last_error: Optional[Exception] = None

        for attempt in range(1, MAX_DOC_WRITE_ATTEMPTS + 1):
            try:
                state = _get_doc_state(file_key)
                body = build_request_body(state)

                if not body.get("requests"):
                    return {"status": "skipped", "reason": "no_requests"}

                return _get_docs().documents().batchUpdate(
                    documentId=file_id,
                    body=body,
                ).execute()
            except Exception as exc:
                last_error = exc

                if attempt >= MAX_DOC_WRITE_ATTEMPTS or not _is_retryable_docs_error(exc):
                    raise

                delay = _retry_delay_seconds(attempt)
                logger.warning(
                    "Retrying %s for %s after attempt %s failed: %s",
                    operation_name,
                    file_key,
                    attempt,
                    exc,
                )
                time.sleep(delay)

        if last_error:
            raise last_error

        raise RuntimeError(f"{operation_name} failed without an explicit error")


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


def append_doc_text(file_key: str, content: str) -> None:
    """
    Append text to the end of a Google Doc using the Docs API directly.
    This avoids stale index races by targeting the current revision and
    inserting at the document body's end instead of computing a hard index.
    """
    clean = _normalize_text(content)
    if not clean:
        return

    def build_request_body(state: Dict[str, Any]) -> Dict[str, Any]:
        prefix = "\n\n" if state["end_index"] > 1 else ""
        body: Dict[str, Any] = {
            "requests": [
                {
                    "insertText": {
                        "endOfSegmentLocation": {},
                        "text": f"{prefix}{clean}",
                    }
                }
            ]
        }

        if state["revision_id"]:
            body["writeControl"] = {
                "targetRevisionId": state["revision_id"],
            }

        return body

    _run_docs_write(file_key, "append_doc_text", build_request_body)


def replace_doc_text(file_key: str, content: str) -> None:
    """
    Replace the full content of a Google Doc using Docs API operations.
    This preserves sane formatting far better than whole-file Drive replacement.
    """
    clean = _normalize_text(content)

    def build_request_body(state: Dict[str, Any]) -> Dict[str, Any]:
        requests = []

        if state["end_index"] > 2:
            requests.append(
                {
                    "deleteContentRange": {
                        "range": {
                            "startIndex": 1,
                            "endIndex": state["end_index"] - 1,
                        }
                    }
                }
            )

        if clean:
            requests.append(
                {
                    "insertText": {
                        "location": {"index": 1},
                        "text": clean,
                    }
                }
            )

        body: Dict[str, Any] = {"requests": requests}

        if state["revision_id"]:
            body["writeControl"] = {
                "requiredRevisionId": state["revision_id"],
            }

        return body

    _run_docs_write(file_key, "replace_doc_text", build_request_body)


def _append_entries(file_key: str, entries: Optional[List[str]]) -> int:
    written = 0

    for entry in _clean_array(entries):
        append_doc_text(file_key, entry)
        written += 1

    return written


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
    errors = {}

    for key in [
        "core_continuity",
        "interaction_learning",
        "emotional_snapshot",
        "cognitive_tuning",
    ]:
        try:
            memory[key] = export_doc_text(key)
        except Exception as e:
            errors[key] = str(e)

    return {
        "status": "memory_loaded",
        "memory": memory,
        "errors": errors,
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
    replace_doc_text(file_key, content)
    return {
        "status": "memory_replaced",
        "file_key": file_key,
    }


@mcp.tool()
def end_session_sweep(
    core_continuity_entries: Optional[List[str]] = None,
    interaction_learning_entries: Optional[List[str]] = None,
    emotional_snapshot_content: Optional[str] = None,
    session_reflections_entries: Optional[List[str]] = None,
    cognitive_tuning_entries: Optional[List[str]] = None,
    stop_on_error: bool = True,
) -> Dict[str, Any]:
    """
    Perform a five-log memory sweep in one server-side call.

    Writes are processed sequentially in this order:
    - core_continuity append(s)
    - interaction_learning append(s)
    - emotional_snapshot replace
    - session_reflections append(s)
    - cognitive_tuning append(s)

    This is intended to reduce client-side flakiness during end-of-session
    logging while still preserving one-log-at-a-time reliability on the server.
    Any omitted or blank payload is skipped rather than forced.
    """
    operations = [
        {
            "file_key": "core_continuity",
            "operation": "append",
            "entries": core_continuity_entries,
        },
        {
            "file_key": "interaction_learning",
            "operation": "append",
            "entries": interaction_learning_entries,
        },
        {
            "file_key": "emotional_snapshot",
            "operation": "replace",
            "content": emotional_snapshot_content,
        },
        {
            "file_key": "session_reflections",
            "operation": "append",
            "entries": session_reflections_entries,
        },
        {
            "file_key": "cognitive_tuning",
            "operation": "append",
            "entries": cognitive_tuning_entries,
        },
    ]

    results: List[Dict[str, Any]] = []
    total_write_operations = 0

    for spec in operations:
        file_key = spec["file_key"]
        operation = spec["operation"]

        try:
            if operation == "replace":
                content = spec.get("content")

                if content is None:
                    results.append(
                        {
                            "file_key": file_key,
                            "operation": operation,
                            "status": "skipped",
                            "reason": "no_content_provided",
                        }
                    )
                    continue

                clean_content = _normalize_text(content)

                if not clean_content:
                    results.append(
                        {
                            "file_key": file_key,
                            "operation": operation,
                            "status": "skipped",
                            "reason": "blank_content_provided",
                        }
                    )
                    continue

                replace_doc_text(file_key, clean_content)
                total_write_operations += 1
                results.append(
                    {
                        "file_key": file_key,
                        "operation": operation,
                        "status": "written",
                        "writes": 1,
                    }
                )
                continue

            entries = _clean_array(spec.get("entries"))

            if not entries:
                results.append(
                    {
                        "file_key": file_key,
                        "operation": operation,
                        "status": "skipped",
                        "reason": "no_entries_provided",
                    }
                )
                continue

            writes = _append_entries(file_key, entries)
            total_write_operations += writes
            results.append(
                {
                    "file_key": file_key,
                    "operation": operation,
                    "status": "written",
                    "writes": writes,
                }
            )
        except Exception as exc:
            failure = {
                "file_key": file_key,
                "operation": operation,
                "status": "failed",
                "error": str(exc),
            }
            results.append(failure)

            if stop_on_error:
                return {
                    "status": "sweep_partial",
                    "total_write_operations": total_write_operations,
                    "failed_step": failure,
                    "results": results,
                }

    if total_write_operations == 0:
        return {
            "status": "noop",
            "total_write_operations": 0,
            "results": results,
        }

    return {
        "status": "sweep_complete",
        "total_write_operations": total_write_operations,
        "results": results,
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


# Export MCP app
app = mcp.http_app(path="/mcp/")
