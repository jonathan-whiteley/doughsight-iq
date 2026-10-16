"""Genie One: streams the onechat endpoint (the backend behind the Genie One MCP) as the signed-in user."""

import logging
import os
from typing import Any, Callable, Dict, Iterator, Optional, Tuple

import requests
from databricks.sdk.core import Config

from services.genie_one_parser import OneChatParser, parse_line

logger = logging.getLogger(__name__)

ONECHAT_PATH = "/api/2.0/data-rooms/tools/onechat/responses"
SOURCE: Optional[str] = "doughsight_iq"  # None if the Step 1 probe showed the field is rejected
AUTH_MESSAGE = "Genie One needs user authorization for this app. Open the app URL while signed in, or add the genie user scope."
DISABLED_MESSAGE = "Genie One is not enabled in this workspace."


def build_body(question: str, conversation_id: Optional[str]) -> Dict[str, Any]:
    body: Dict[str, Any] = {"input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": question}]}], "enable_viz": False}
    if SOURCE:
        body["source"] = SOURCE
    if conversation_id:
        body["conversationId"] = conversation_id
    return body


class MissingUserToken(Exception):
    """Inside Databricks Apps but no forwarded user token (would otherwise run as the app service principal)."""


def resolve_auth(forwarded_token: Optional[str]) -> Tuple[str, Dict[str, str]]:
    """Signed-in user's token inside Databricks Apps; local CLI profile otherwise."""
    cfg = Config()
    host = cfg.host.rstrip("/")
    if forwarded_token:
        return host, {"Authorization": f"Bearer {forwarded_token}"}
    if os.environ.get("DATABRICKS_APP_NAME"):
        raise MissingUserToken(AUTH_MESSAGE)
    return host, cfg.authenticate()


def _http_error(status: int, text: str) -> Dict[str, Any]:
    if status in (401, 403):
        return {"type": "error", "kind": "auth", "message": AUTH_MESSAGE}
    if status == 404:
        return {"type": "error", "kind": "disabled", "message": DISABLED_MESSAGE}
    return {"type": "error", "kind": "upstream", "message": f"Genie One returned HTTP {status}: {text[:300]}"}


def stream_events(question: str, conversation_id: Optional[str], host: str, headers: Dict[str, str],
                  post: Callable[..., Any] = requests.post) -> Iterator[Dict[str, Any]]:
    try:
        resp = post(host + ONECHAT_PATH, json=build_body(question, conversation_id),
                    headers={**headers, "Accept": "text/event-stream"}, stream=True, timeout=(10, 300))
    except requests.RequestException as e:
        yield {"type": "error", "kind": "upstream", "message": f"Could not reach Genie One: {e}"}
        return
    if resp.status_code >= 400:
        logger.warning(f"Genie One HTTP {resp.status_code}: {resp.text[:300]}")
        yield _http_error(resp.status_code, resp.text)
        return

    parser = OneChatParser()
    saw_done = False
    try:
        # Decode as UTF-8 ourselves: text/event-stream has no charset, so requests would guess latin-1.
        for raw in resp.iter_lines():
            line = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
            ev = parse_line(line) if line else None
            if ev is None:
                continue
            for out in parser.feed(ev):
                saw_done = saw_done or out["type"] == "done"
                yield out
    except requests.RequestException as e:
        yield {"type": "error", "kind": "upstream", "message": f"Connection to Genie One lost: {e}"}
    except Exception as e:
        logger.exception("Genie One stream failed")
        yield {"type": "error", "kind": "upstream", "message": f"Genie One stream failed: {e}"}
    finally:
        resp.close()
    if not saw_done:
        yield {"type": "done"}
