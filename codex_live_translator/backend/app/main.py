import json
import logging
import time
import uuid
from pathlib import Path

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .models import (
    RealtimeConnectRequest,
    SegmentProcessResponse,
    SegmentRecord,
    SessionEndRequest,
    SessionEndResponse,
    SessionStartRequest,
    SessionStartResponse,
    TextTranslateRequest,
)
from .services.factory import build_processor
from .store import Store, utc_now

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

settings = get_settings()
store = Store(settings.db_path)
processor = build_processor(settings)

app = FastAPI(title=settings.app_name)

origins = [item.strip() for item in settings.cors_allow_origins.split(",") if item.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client_dir = Path(__file__).resolve().parents[2] / "client"
if client_dir.exists():
    app.mount("/client", StaticFiles(directory=client_dir), name="client")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "provider": settings.provider}


@app.get("/")
async def root() -> FileResponse:
    index_path = client_dir / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Client not found")
    return FileResponse(index_path)


@app.get("/manifest.webmanifest")
async def manifest() -> FileResponse:
    manifest_path = client_dir / "manifest.webmanifest"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Manifest not found")
    return FileResponse(manifest_path, media_type="application/manifest+json")


@app.get("/sw.js")
async def service_worker() -> FileResponse:
    sw_path = client_dir / "sw.js"
    if not sw_path.exists():
        raise HTTPException(status_code=404, detail="Service worker not found")
    return FileResponse(
        sw_path,
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/"},
    )


@app.post("/v1/session/start", response_model=SessionStartResponse)
async def start_session(request: SessionStartRequest) -> SessionStartResponse:
    session_id = str(uuid.uuid4())
    record = store.create_session(
        session_id=session_id,
        project_name=request.project_name,
        source_lang_hint=request.source_lang_hint,
        target_lang=request.target_lang,
        mode=request.mode,
    )
    return SessionStartResponse(session_id=record.session_id, started_at=record.created_at)


@app.post("/v1/realtime/connect")
async def connect_realtime(request: RealtimeConnectRequest) -> PlainTextResponse:
    session = store.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Unknown session_id")

    if settings.provider.strip().lower() != "openai" or not settings.openai_api_key:
        raise HTTPException(
            status_code=400,
            detail="Realtime mode requires FT_PROVIDER=openai and FT_OPENAI_API_KEY",
        )

    offer_sdp = request.offer_sdp
    if not offer_sdp or not offer_sdp.strip():
        raise HTTPException(status_code=400, detail="offer_sdp is required")

    source_lang = (request.source_lang_hint or session.source_lang_hint or "auto").strip()
    transcription_config: dict[str, str] = {"model": settings.openai_transcribe_model}
    if source_lang and source_lang != "auto":
        transcription_config["language"] = source_lang

    transcription_session = {
        "type": "transcription",
        "audio": {
            "input": {
                "transcription": transcription_config,
                "turn_detection": {
                    "type": "server_vad",
                    "silence_duration_ms": 600,
                },
                "noise_reduction": {"type": "near_field"},
            }
        },
    }

    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    files = {
        "sdp": (None, offer_sdp),
        "session": (
            None,
            json.dumps(transcription_session),
        ),
    }

    try:
        async with httpx.AsyncClient(timeout=settings.segment_timeout_seconds) as client:
            response = await client.post(
                "https://api.openai.com/v1/realtime/calls",
                headers=headers,
                files=files,
            )
    except Exception as exc:  # noqa: BLE001
        logger.exception("realtime connection failed")
        raise HTTPException(status_code=502, detail=f"Provider failed: {exc}") from exc

    if response.status_code >= 400:
        detail = _extract_error_message(response)
        raise HTTPException(status_code=502, detail=f"Provider failed: {detail}")

    answer_sdp = _normalize_sdp(response.text)
    if not answer_sdp:
        raise HTTPException(status_code=502, detail="Provider failed: Empty SDP answer")
    if "v=0" not in answer_sdp or "m=audio" not in answer_sdp:
        snippet = answer_sdp[:240].replace("\r", "\\r").replace("\n", "\\n")
        raise HTTPException(status_code=502, detail=f"Provider failed: Invalid SDP answer ({snippet})")

    call_id = response.headers.get("x-openai-call-id")
    headers: dict[str, str] = {}
    if call_id:
        headers["x-openai-call-id"] = call_id
    return PlainTextResponse(answer_sdp, media_type="application/sdp", headers=headers)


@app.post("/v1/segment/process", response_model=SegmentProcessResponse)
async def process_segment(
    session_id: str = Form(...),
    segment_id: str = Form(...),
    started_at_ms: int = Form(...),
    ended_at_ms: int = Form(...),
    prior_context_json: str | None = Form(default=None),
    conversation_context: str | None = Form(default=None),
    source_lang_hint: str | None = Form(default=None),
    target_lang: str | None = Form(default=None),
    audio_file: UploadFile = File(...),
) -> SegmentProcessResponse:
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Unknown session_id")

    if ended_at_ms < started_at_ms:
        raise HTTPException(status_code=400, detail="ended_at_ms must be >= started_at_ms")

    try:
        prior_context_raw = json.loads(prior_context_json) if prior_context_json else []
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="prior_context_json must be valid JSON") from exc

    if not isinstance(prior_context_raw, list):
        raise HTTPException(status_code=400, detail="prior_context_json must decode to a list")

    prior_context = [str(line) for line in prior_context_raw[-settings.max_context_lines :]]
    conversation_context = (conversation_context or "").strip()

    chosen_source_lang = (source_lang_hint or session.source_lang_hint or "auto").strip()
    chosen_target_lang = (target_lang or session.target_lang or "en").strip()

    audio_bytes = await audio_file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="audio_file is empty")

    processing_started = time.perf_counter()
    try:
        processed = await processor.process(
            audio_bytes=audio_bytes,
            mime_type=audio_file.content_type or "audio/webm",
            source_lang=chosen_source_lang,
            target_lang=chosen_target_lang,
            prior_context=prior_context,
            conversation_context=conversation_context,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("segment processing failed")
        raise HTTPException(status_code=502, detail=f"Provider failed: {exc}") from exc

    latency_ms = int((time.perf_counter() - processing_started) * 1000)
    store.upsert_segment(
        SegmentRecord(
            session_id=session_id,
            segment_id=segment_id,
            t_start_ms=started_at_ms,
            t_end_ms=ended_at_ms,
            transcript_src=processed.transcript_src,
            translation_en=processed.translation_en,
            confidence=processed.confidence,
            latency_ms=latency_ms,
            finalized=processed.is_final,
            created_at=utc_now(),
        )
    )

    return SegmentProcessResponse(
        segment_id=segment_id,
        transcript_src=processed.transcript_src,
        translation_en=processed.translation_en,
        confidence=processed.confidence,
        latency_ms=latency_ms,
        is_final=processed.is_final,
    )


@app.post("/v1/text/translate", response_model=SegmentProcessResponse)
async def translate_text(request: TextTranslateRequest) -> SegmentProcessResponse:
    session = store.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Unknown session_id")

    if not request.segment_id.strip():
        raise HTTPException(status_code=400, detail="segment_id is required")

    if request.ended_at_ms < request.started_at_ms:
        raise HTTPException(status_code=400, detail="ended_at_ms must be >= started_at_ms")

    transcript = request.transcript_src.strip()
    if not transcript:
        raise HTTPException(status_code=400, detail="transcript_src is empty")

    prior_context = [str(line) for line in request.prior_context_json[-settings.max_context_lines :]]
    conversation_context = (request.conversation_context or "").strip()

    chosen_source_lang = (request.source_lang_hint or session.source_lang_hint or "auto").strip()
    chosen_target_lang = (request.target_lang or session.target_lang or "en").strip()

    processing_started = time.perf_counter()
    try:
        translation = await processor.translate_text(
            transcript=transcript,
            source_lang=chosen_source_lang,
            target_lang=chosen_target_lang,
            prior_context=prior_context,
            conversation_context=conversation_context,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("text translation failed")
        raise HTTPException(status_code=502, detail=f"Provider failed: {exc}") from exc

    latency_ms = int((time.perf_counter() - processing_started) * 1000)
    store.upsert_segment(
        SegmentRecord(
            session_id=request.session_id,
            segment_id=request.segment_id,
            t_start_ms=request.started_at_ms,
            t_end_ms=request.ended_at_ms,
            transcript_src=transcript,
            translation_en=translation,
            confidence=0.7 if settings.provider.strip().lower() == "openai" else 0.25,
            latency_ms=latency_ms,
            finalized=request.is_final,
            created_at=utc_now(),
        )
    )

    return SegmentProcessResponse(
        segment_id=request.segment_id,
        transcript_src=transcript,
        translation_en=translation,
        confidence=0.7 if settings.provider.strip().lower() == "openai" else 0.25,
        latency_ms=latency_ms,
        is_final=request.is_final,
    )


@app.post("/v1/session/end", response_model=SessionEndResponse)
async def end_session(request: SessionEndRequest) -> SessionEndResponse:
    session = store.end_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Unknown session_id")

    ended_at = session.ended_at or utc_now()
    duration_ms = int((ended_at - session.created_at).total_seconds() * 1000)
    segments_count = store.get_segment_count(request.session_id)

    return SessionEndResponse(
        session_id=request.session_id,
        duration_ms=max(0, duration_ms),
        segments_count=segments_count,
    )


@app.get("/v1/session/{session_id}/export")
async def export_session(
    session_id: str,
    format: str = Query(default="json", pattern="^(json|csv|srt)$"),
):
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Unknown session_id")

    if format == "json":
        payload = store.export_json(session_id)
        return PlainTextResponse(payload, media_type="application/json")

    if format == "csv":
        payload = store.export_csv(session_id)
        return PlainTextResponse(
            payload,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{session_id}.csv"',
            },
        )

    payload = store.export_srt(session_id)
    return PlainTextResponse(
        payload,
        media_type="application/x-subrip",
        headers={
            "Content-Disposition": f'attachment; filename="{session_id}.srt"',
        },
    )


def _extract_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip()[:300] or response.reason_phrase

    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            err_type = error.get("type")
            code = error.get("code")
            details = [
                part
                for part in [
                    str(err_type) if err_type else "",
                    str(code) if code else "",
                    str(message) if message else "",
                ]
                if part
            ]
            if details:
                return " | ".join(details)

    return str(payload)[:300]


def _normalize_sdp(raw_sdp: str) -> str:
    if not raw_sdp:
        return ""
    cleaned = raw_sdp.replace("\ufeff", "")
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line for line in cleaned.split("\n") if line.strip()]
    if not lines:
        return ""
    return "\r\n".join(lines) + "\r\n"
