import importlib
import json

from fastapi.testclient import TestClient


def build_client(tmp_path, monkeypatch):
    monkeypatch.setenv("FT_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("FT_PROVIDER", "mock")

    import app.main as main

    main = importlib.reload(main)
    return TestClient(main.app)


def test_end_to_end_session(tmp_path, monkeypatch):
    client = build_client(tmp_path, monkeypatch)

    manifest_response = client.get("/manifest.webmanifest")
    assert manifest_response.status_code == 200

    sw_response = client.get("/sw.js")
    assert sw_response.status_code == 200

    start_response = client.post(
        "/v1/session/start",
        json={
            "project_name": "street-doc",
            "source_lang_hint": "ja",
            "target_lang": "en",
            "mode": "balanced",
        },
    )
    assert start_response.status_code == 200
    session_id = start_response.json()["session_id"]

    seg_response = client.post(
        "/v1/segment/process",
        data={
            "session_id": session_id,
            "segment_id": "seg-1",
            "started_at_ms": "0",
            "ended_at_ms": "8000",
            "prior_context_json": json.dumps(["hello context"]),
            "source_lang_hint": "ja",
            "target_lang": "en",
        },
        files={"audio_file": ("seg.webm", b"abc123", "audio/webm")},
    )
    assert seg_response.status_code == 200
    payload = seg_response.json()
    assert payload["segment_id"] == "seg-1"
    assert payload["translation_en"]

    realtime_connect_response = client.post(
        "/v1/realtime/connect",
        json={
            "session_id": session_id,
            "offer_sdp": "v=0",
            "source_lang_hint": "ja",
        },
    )
    assert realtime_connect_response.status_code == 400
    assert "requires FT_PROVIDER=openai" in realtime_connect_response.text

    text_translate_response = client.post(
        "/v1/text/translate",
        json={
            "session_id": session_id,
            "segment_id": "seg-2",
            "transcript_src": "konnichiwa",
            "started_at_ms": 8000,
            "ended_at_ms": 12000,
            "prior_context_json": ["hello context"],
            "source_lang_hint": "ja",
            "target_lang": "en",
            "conversation_context": "street interview",
            "is_final": False,
        },
    )
    assert text_translate_response.status_code == 200
    text_payload = text_translate_response.json()
    assert text_payload["segment_id"] == "seg-2"
    assert text_payload["translation_en"]
    assert text_payload["is_final"] is False

    end_response = client.post("/v1/session/end", json={"session_id": session_id})
    assert end_response.status_code == 200
    assert end_response.json()["segments_count"] == 2

    export_response = client.get(f"/v1/session/{session_id}/export?format=json")
    assert export_response.status_code == 200
    exported = export_response.json()
    assert exported["session"]["session_id"] == session_id
    assert len(exported["segments"]) == 2
