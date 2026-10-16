import json

from services import genie_one_service as g1


def sse_events(text):
    return [json.loads(chunk[len("data: "):]) for chunk in text.split("\n\n") if chunk.startswith("data: ")]


def test_blank_question_rejected(client, monkeypatch):
    called = []
    monkeypatch.setattr(g1, "stream_events", lambda *a, **k: called.append(1) or iter(()))
    r = client.post("/api/genie-one/ask", json={"question": "   "})
    assert r.status_code == 400 and not called


def test_streams_sse_with_forwarded_token(client, monkeypatch):
    seen = {}

    def fake_auth(token):
        seen["token"] = token
        return "https://h", {"Authorization": f"Bearer {token}"}

    def fake_stream(question, conversation_id, host, headers):
        seen.update(question=question, conversation_id=conversation_id)
        yield {"type": "meta", "conversation_id": "c1"}
        yield {"type": "done"}

    monkeypatch.setattr(g1, "resolve_auth", fake_auth)
    monkeypatch.setattr(g1, "stream_events", fake_stream)
    r = client.post("/api/genie-one/ask", json={"question": "Revenue?", "conversation_id": "c0"},
                    headers={"X-Forwarded-Access-Token": "user-tok"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert sse_events(r.text) == [{"type": "meta", "conversation_id": "c1"}, {"type": "done"}]
    assert seen == {"token": "user-tok", "question": "Revenue?", "conversation_id": "c0"}


def test_auth_resolution_failure_is_streamed(client, monkeypatch):
    def broken(token):
        raise ValueError("no credentials")
    monkeypatch.setattr(g1, "resolve_auth", broken)
    events = sse_events(client.post("/api/genie-one/ask", json={"question": "x"}).text)
    assert events[0]["type"] == "error" and "no credentials" in events[0]["message"]


def test_in_app_without_token_is_auth_error_and_no_upstream_call(client, monkeypatch):
    class Cfg:
        host = "https://ws.example.com"
        def authenticate(self):
            raise AssertionError("must not use the service principal")
    called = []
    monkeypatch.setattr(g1, "Config", lambda: Cfg())
    monkeypatch.setattr(g1, "stream_events", lambda *a, **k: called.append(1) or iter(()))
    monkeypatch.setenv("DATABRICKS_APP_NAME", "doughsight-iq")
    events = sse_events(client.post("/api/genie-one/ask", json={"question": "x"}).text)
    assert events == [{"type": "error", "kind": "auth", "message": g1.AUTH_MESSAGE}]
    assert not called
