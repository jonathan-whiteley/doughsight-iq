"""Genie One endpoint: streams normalized onechat events to the browser as SSE."""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config.settings import settings
from services import genie_one_service as g1

logger = logging.getLogger(__name__)
router = APIRouter()


class OneAskRequest(BaseModel):
    question: str
    conversation_id: Optional[str] = None


@router.get("/genie-one/config")
def genie_one_config():
    """catalog.schema the starter questions point Genie One at."""
    return {"schema_fqn": settings.table_prefix}


@router.post("/genie-one/ask")
def genie_one_ask(request: OneAskRequest, x_forwarded_access_token: Optional[str] = Header(default=None)):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is empty")

    def events():
        try:
            host, headers = g1.resolve_auth(x_forwarded_access_token)
        except g1.MissingUserToken:
            yield {"type": "error", "kind": "auth", "message": g1.AUTH_MESSAGE}
            return
        except Exception as e:
            logger.error(f"Genie One auth failed: {e}")
            yield {"type": "error", "kind": "auth", "message": f"Could not authenticate to Databricks: {e}"}
            return
        yield from g1.stream_events(question, request.conversation_id, host, headers)

    def sse():
        for ev in events():
            yield f"data: {json.dumps(ev)}\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
