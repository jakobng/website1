from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, Field


class SessionStartRequest(BaseModel):
    project_name: str = Field(default="untitled")
    source_lang_hint: str = Field(default="auto")
    target_lang: str = Field(default="en")
    mode: str = Field(default="balanced")


class SessionStartResponse(BaseModel):
    session_id: str
    started_at: datetime


class SessionEndRequest(BaseModel):
    session_id: str


class SessionEndResponse(BaseModel):
    session_id: str
    duration_ms: int
    segments_count: int


class SegmentProcessResponse(BaseModel):
    segment_id: str
    transcript_src: str
    translation_en: str
    confidence: float
    latency_ms: int
    is_final: bool


class TextTranslateRequest(BaseModel):
    session_id: str
    segment_id: str
    transcript_src: str
    started_at_ms: int
    ended_at_ms: int
    prior_context_json: list[str] = Field(default_factory=list)
    source_lang_hint: str = Field(default="auto")
    target_lang: str = Field(default="en")
    conversation_context: str = Field(default="")


class RealtimeConnectRequest(BaseModel):
    session_id: str
    offer_sdp: str
    source_lang_hint: str = Field(default="auto")


class RealtimeConnectResponse(BaseModel):
    answer_sdp: str
    call_id: str | None = None


@dataclass(slots=True)
class SessionRecord:
    session_id: str
    project_name: str
    source_lang_hint: str
    target_lang: str
    mode: str
    created_at: datetime
    ended_at: datetime | None


@dataclass(slots=True)
class SegmentRecord:
    session_id: str
    segment_id: str
    t_start_ms: int
    t_end_ms: int
    transcript_src: str
    translation_en: str
    confidence: float
    latency_ms: int
    finalized: bool
    created_at: datetime
