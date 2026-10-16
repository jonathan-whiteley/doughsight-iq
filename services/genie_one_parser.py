"""Normalizes Genie One (onechat) stream events into the small event set the UI renders.

The onechat API is undocumented (it backs `databricks genie ask` and the Genie One MCP),
so every field access is defensive and unknown event types are dropped.
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple, Union

EMBED_RE = re.compile(r"<!-- begin-embedded:(query_[\w-]+) -->\n?(.*?)\n?<!-- end-embedded:\1 -->", re.S)
ASSET_PREFIX_RE = re.compile(r"^(table|view|metric_view|function|volume|dashboard|genie_space)\.")


def parse_line(line: Union[str, bytes]) -> Optional[Dict[str, Any]]:
    """One SSE or JSON-lines line to an event dict; None for anything that is not a JSON object."""
    if isinstance(line, bytes):
        line = line.decode("utf-8", "replace")
    s = line.strip()
    if s.startswith("data:"):
        s = s[5:].strip()
    if not s.startswith("{"):
        return None
    try:
        ev = json.loads(s)
    except ValueError:
        return None
    return ev if isinstance(ev, dict) else None


def split_answer(text: str) -> List[Dict[str, str]]:
    """Split the final answer into markdown and embedded-query segments."""
    segments: List[Dict[str, str]] = []
    pos = 0
    for m in EMBED_RE.finditer(text):
        before = text[pos:m.start()].strip()
        if before:
            segments.append({"type": "markdown", "text": before})
        segments.append({"type": "query", "id": m.group(1), "markdown": m.group(2).strip()})
        pos = m.end()
    rest = text[pos:].strip()
    if rest:
        segments.append({"type": "markdown", "text": rest})
    return segments


def _args(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def describe_call(name: str, args: Dict[str, Any]) -> Tuple[str, str, Optional[str]]:
    """(kind, label, detail) for a Genie One tool call."""
    if name == "execute_sql_query":
        return "sql", "Running SQL", str(args.get("query") or "") or None
    if name == "get_asset_info":
        asset = ASSET_PREFIX_RE.sub("", str(args.get("asset") or ""))
        return "read", f"Reading {asset}" if asset else "Reading asset", None
    if name.startswith("search"):
        base = "Searching knowledge" if "knowledge" in name else "Searching assets"
        q = args.get("query")
        return "search", f'{base}: "{q}"' if q else base, None
    return "other", (name.replace("_", " ").capitalize() or "Working"), None


def _int(v: Any) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _in_progress(output: str) -> bool:
    if not output.startswith("{"):
        return False
    try:
        return json.loads(output).get("status") == "in_progress"
    except (ValueError, AttributeError):
        return False


class OneChatParser:
    def __init__(self) -> None:
        self.conversation_id: Optional[str] = None
        self._calls: Dict[str, Dict[str, Optional[str]]] = {}
        self._results: set = set()
        self._messages: set = set()

    def feed(self, event: Dict[str, Any]) -> List[Dict[str, Any]]:
        try:
            return self._feed(event)
        except Exception:  # never let one odd event kill the stream
            return []

    def _feed(self, event: Dict[str, Any]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        cid = event.get("conversation_id")
        if cid and not self.conversation_id:
            self.conversation_id = cid
            out.append({"type": "meta", "conversation_id": cid})

        etype = str(event.get("type") or "")
        if etype == "response.done":
            status = (event.get("response") or {}).get("status") or "completed"
            if status != "completed":
                out.append({"type": "error", "kind": "upstream", "message": f"Genie One ended with status {status}"})
            out.append({"type": "done"})
            return out
        if etype in ("error", "response.failed", "response.error"):
            err = event.get("error")
            msg = event.get("message") or (err.get("message") if isinstance(err, dict) else err) or "Genie One returned an error"
            out.append({"type": "error", "kind": "upstream", "message": str(msg)})
            return out
        if not etype.startswith("response.output_item."):
            return out

        item = event.get("item")
        if not isinstance(item, dict):
            return out
        meta = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        itype = item.get("type")

        if itype == "function_call":
            call_id = item.get("call_id") or item.get("id")
            if not call_id or call_id in self._calls:
                return out
            kind, label, detail = describe_call(str(item.get("name") or ""), _args(item.get("arguments")))
            self._calls[call_id] = {"sql": detail if kind == "sql" else None}
            out.append({"type": "step", "id": call_id, "kind": kind, "label": label, "detail": detail})

        elif itype == "function_call_output":
            call_id = item.get("call_id")
            text = str(item.get("output") or "")
            if not call_id or not text or _in_progress(text) or (call_id, text) in self._results:
                return out
            self._results.add((call_id, text))
            out.append({"type": "step_result", "id": call_id, "summary": text.split("\n", 1)[0].rstrip(":")[:200]})
            rd, embed_id = meta.get("result_data"), meta.get("embed_id")
            if isinstance(rd, dict) and embed_id:
                out.append({
                    "type": "query",
                    "id": embed_id,
                    "call_id": call_id,
                    "sql": (self._calls.get(call_id) or {}).get("sql"),
                    "columns": [{"name": c.get("name"), "type": c.get("type_text") or c.get("type") or ""}
                                for c in rd.get("columns") or [] if isinstance(c, dict) and c.get("name")],
                    "rows": rd.get("preview_rows") or [],
                    "total_row_count": _int(rd.get("total_row_count")),
                })

        elif itype == "message":
            content = item.get("content") if isinstance(item.get("content"), list) else []
            text = "".join(str(c.get("text") or "") for c in content if isinstance(c, dict)).strip()
            mid = item.get("id") or text
            if not text or mid in self._messages:
                return out
            self._messages.add(mid)
            if meta.get("ui_type") == "FINAL_RESPONSE":
                out.append({"type": "answer", "segments": split_answer(text)})
            else:
                out.append({"type": "thinking", "text": text})
        return out
