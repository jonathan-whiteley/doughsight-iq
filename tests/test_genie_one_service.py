import json

import pytest
import requests

from services import genie_one_service as g1


class FakeResp:
    def __init__(self, status_code=200, lines=(), text="", raise_after=None):
        self.status_code = status_code
        self._lines = list(lines)
        self.text = text
        self.raise_after = raise_after
        self.closed = False

    def iter_lines(self, decode_unicode=False):
        for i, line in enumerate(self._lines):
            if self.raise_after is not None and i == self.raise_after:
                raise requests.ConnectionError("reset")
            yield line

    def close(self):
        self.closed = True


def fake_post(resp, seen=None):
    def post(url, json=None, headers=None, stream=None, timeout=None):
        if seen is not None:
            seen.update(url=url, json=json, headers=headers)
        return resp
    return post


def collect(resp, seen=None, conversation_id=None):
    return list(g1.stream_events("q?", conversation_id, "https://h", {"Authorization": "Bearer t"}, post=fake_post(resp, seen)))


def fixture_lines(fixtures_dir, name):
    return ["data: " + l for l in (fixtures_dir / name).read_text().splitlines()]


def test_build_body_conversation_only_when_given():
    assert "conversationId" not in g1.build_body("hi", None)
    body = g1.build_body("hi", "c1")
    assert body["conversationId"] == "c1"
    assert body["input"] == [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hi"}]}]
    assert body["enable_viz"] is False


def test_request_shape(fixtures_dir):
    seen = {}
    collect(FakeResp(lines=fixture_lines(fixtures_dir, "onechat_followup.jsonl")), seen, conversation_id="c9")
    assert seen["url"] == "https://h" + g1.ONECHAT_PATH
    assert seen["headers"]["Authorization"] == "Bearer t"
    assert seen["json"]["conversationId"] == "c9"


def test_full_stream_from_fixture(fixtures_dir):
    out = collect(FakeResp(lines=fixture_lines(fixtures_dir, "onechat_turn1.jsonl")))
    types = [e["type"] for e in out]
    assert types[0] == "meta" and types[-1] == "done" and "answer" in types
    assert types.count("done") == 1


def test_auth_error():
    out = collect(FakeResp(status_code=403, text="forbidden"))
    assert out == [{"type": "error", "kind": "auth", "message": g1.AUTH_MESSAGE}]


def test_disabled_error():
    out = collect(FakeResp(status_code=404, text="not found"))
    assert out[0]["kind"] == "disabled"


def test_upstream_error_includes_body():
    out = collect(FakeResp(status_code=500, text="boom happened"))
    assert out[0]["kind"] == "upstream" and "boom happened" in out[0]["message"]


def test_truncated_stream_still_ends_with_done(fixtures_dir):
    out = collect(FakeResp(lines=fixture_lines(fixtures_dir, "onechat_turn1.jsonl")[:10]))
    assert out[-1] == {"type": "done"}
    assert "answer" not in [e["type"] for e in out]


def test_connection_drop_mid_stream(fixtures_dir):
    resp = FakeResp(lines=fixture_lines(fixtures_dir, "onechat_turn1.jsonl"), raise_after=5)
    out = collect(resp)
    assert any(e["type"] == "error" and e["kind"] == "upstream" for e in out)
    assert out[-1] == {"type": "done"} and resp.closed


def test_post_raises():
    def boom(*a, **k):
        raise requests.ConnectionError("dns")
    out = list(g1.stream_events("q", None, "https://h", {}, post=boom))
    assert out[0]["kind"] == "upstream"


def test_resolve_auth_prefers_forwarded_token(monkeypatch):
    class Cfg:
        host = "https://ws.example.com/"
        def authenticate(self):
            return {"Authorization": "Bearer sp"}
    monkeypatch.setattr(g1, "Config", lambda: Cfg())
    assert g1.resolve_auth("user-tok") == ("https://ws.example.com", {"Authorization": "Bearer user-tok"})
    monkeypatch.delenv("DATABRICKS_APP_NAME", raising=False)
    assert g1.resolve_auth(None) == ("https://ws.example.com", {"Authorization": "Bearer sp"})


def test_resolve_auth_in_app_requires_user_token(monkeypatch):
    class Cfg:
        host = "https://ws.example.com/"
        def authenticate(self):
            raise AssertionError("must not use the service principal")
    monkeypatch.setattr(g1, "Config", lambda: Cfg())
    monkeypatch.setenv("DATABRICKS_APP_NAME", "doughsight-iq")
    with pytest.raises(g1.MissingUserToken):
        g1.resolve_auth(None)
    assert g1.resolve_auth("tok")[1] == {"Authorization": "Bearer tok"}


def _msg_line(text, ui_type, mid):
    ev = {"type": "response.output_item.added", "item": {"type": "message", "role": "assistant", "id": mid,
          "content": [{"type": "output_text", "text": text}], "metadata": {"ui_type": ui_type}}}
    return ("data: " + json.dumps(ev, ensure_ascii=False)).encode("utf-8")


def test_bytes_lines_decoded_as_utf8():
    thought = "Checking caf\u00e9 revenue \u2014 by brand"
    answer = "Total \u2014 caf\u00e9 sales: 9,000"
    lines = [_msg_line(thought, "THOUGHT", "m1"), _msg_line(answer, "FINAL_RESPONSE", "m2")]
    out = collect(FakeResp(lines=lines))
    assert {"type": "thinking", "text": thought} in out
    ans = next(e for e in out if e["type"] == "answer")
    assert ans["segments"] == [{"type": "markdown", "text": answer}]


class ExplodingResp(FakeResp):
    def iter_lines(self, decode_unicode=False):
        yield _msg_line("hello", "THOUGHT", "m1")
        raise ValueError("bad chunk")


def test_non_request_exception_mid_stream():
    resp = ExplodingResp()
    out = collect(resp)
    assert out[0] == {"type": "thinking", "text": "hello"}
    assert out[-2]["type"] == "error" and out[-2]["kind"] == "upstream" and "bad chunk" in out[-2]["message"]
    assert out[-1] == {"type": "done"} and resp.closed
