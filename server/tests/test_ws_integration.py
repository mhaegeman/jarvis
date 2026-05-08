"""End-to-end test: real FastAPI app, real WebSocket, against mock pipelines."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from server.main import app


def test_ws_text_flow_end_to_end() -> None:
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ready = ws.receive_json()
        assert ready["type"] == "ready"
        ws.send_text(json.dumps({"type": "text", "content": "Brief me on today"}))
        types: list[str] = []
        sentences: list[dict[str, str]] = []
        while True:
            data = ws.receive()
            if data.get("text"):
                msg = json.loads(data["text"])
                types.append(msg["type"])
                if msg["type"] == "tts.sentence":
                    sentences.append(msg)
                if msg["type"] == "llm.end":
                    break
            elif data.get("bytes"):
                raise AssertionError("Phase 1 must not emit audio chunks")
        assert "stt.final" in types
        assert "llm.token" in types
        assert sentences


def test_ws_unknown_type_returns_error() -> None:
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        _ = ws.receive_json()  # ready
        ws.send_text(json.dumps({"type": "garbage"}))
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert msg["code"].startswith("protocol.")


def test_health_endpoint() -> None:
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
