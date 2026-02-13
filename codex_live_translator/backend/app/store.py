import csv
import io
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from .models import SegmentRecord, SessionRecord


def utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


class Store:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    project_name TEXT NOT NULL,
                    source_lang_hint TEXT NOT NULL,
                    target_lang TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    ended_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS segments (
                    session_id TEXT NOT NULL,
                    segment_id TEXT NOT NULL,
                    t_start_ms INTEGER NOT NULL,
                    t_end_ms INTEGER NOT NULL,
                    transcript_src TEXT NOT NULL,
                    translation_en TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    latency_ms INTEGER NOT NULL,
                    finalized INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (session_id, segment_id),
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_segments_session_time
                ON segments (session_id, t_start_ms)
                """
            )

    def create_session(
        self,
        session_id: str,
        project_name: str,
        source_lang_hint: str,
        target_lang: str,
        mode: str,
    ) -> SessionRecord:
        created_at = utc_now()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (
                    session_id, project_name, source_lang_hint, target_lang, mode, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    project_name,
                    source_lang_hint,
                    target_lang,
                    mode,
                    created_at.isoformat(),
                ),
            )
        return SessionRecord(
            session_id=session_id,
            project_name=project_name,
            source_lang_hint=source_lang_hint,
            target_lang=target_lang,
            mode=mode,
            created_at=created_at,
            ended_at=None,
        )

    def get_session(self, session_id: str) -> SessionRecord | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            return None
        return SessionRecord(
            session_id=row["session_id"],
            project_name=row["project_name"],
            source_lang_hint=row["source_lang_hint"],
            target_lang=row["target_lang"],
            mode=row["mode"],
            created_at=parse_dt(row["created_at"]) or utc_now(),
            ended_at=parse_dt(row["ended_at"]),
        )

    def end_session(self, session_id: str) -> SessionRecord | None:
        ended_at = utc_now()
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "UPDATE sessions SET ended_at = ? WHERE session_id = ?",
                (ended_at.isoformat(), session_id),
            )
            if cursor.rowcount == 0:
                return None
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            return None
        return SessionRecord(
            session_id=row["session_id"],
            project_name=row["project_name"],
            source_lang_hint=row["source_lang_hint"],
            target_lang=row["target_lang"],
            mode=row["mode"],
            created_at=parse_dt(row["created_at"]) or utc_now(),
            ended_at=parse_dt(row["ended_at"]),
        )

    def upsert_segment(self, record: SegmentRecord) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO segments (
                    session_id,
                    segment_id,
                    t_start_ms,
                    t_end_ms,
                    transcript_src,
                    translation_en,
                    confidence,
                    latency_ms,
                    finalized,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id, segment_id) DO UPDATE SET
                    t_start_ms = excluded.t_start_ms,
                    t_end_ms = excluded.t_end_ms,
                    transcript_src = excluded.transcript_src,
                    translation_en = excluded.translation_en,
                    confidence = excluded.confidence,
                    latency_ms = excluded.latency_ms,
                    finalized = excluded.finalized,
                    created_at = excluded.created_at
                """,
                (
                    record.session_id,
                    record.segment_id,
                    record.t_start_ms,
                    record.t_end_ms,
                    record.transcript_src,
                    record.translation_en,
                    record.confidence,
                    record.latency_ms,
                    1 if record.finalized else 0,
                    record.created_at.isoformat(),
                ),
            )

    def get_segments(self, session_id: str) -> list[SegmentRecord]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM segments WHERE session_id = ? ORDER BY t_start_ms ASC",
                (session_id,),
            ).fetchall()
        return [
            SegmentRecord(
                session_id=row["session_id"],
                segment_id=row["segment_id"],
                t_start_ms=row["t_start_ms"],
                t_end_ms=row["t_end_ms"],
                transcript_src=row["transcript_src"],
                translation_en=row["translation_en"],
                confidence=float(row["confidence"]),
                latency_ms=row["latency_ms"],
                finalized=bool(row["finalized"]),
                created_at=parse_dt(row["created_at"]) or utc_now(),
            )
            for row in rows
        ]

    def get_segment_count(self, session_id: str) -> int:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM segments WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return int(row["count"] if row else 0)

    def export_json(self, session_id: str) -> str:
        session = self.get_session(session_id)
        segments = self.get_segments(session_id)
        payload = {
            "session": {
                "session_id": session.session_id if session else session_id,
                "project_name": session.project_name if session else "",
                "source_lang_hint": session.source_lang_hint if session else "",
                "target_lang": session.target_lang if session else "en",
                "mode": session.mode if session else "",
                "created_at": session.created_at.isoformat() if session else None,
                "ended_at": session.ended_at.isoformat() if session and session.ended_at else None,
            },
            "segments": [
                {
                    "segment_id": seg.segment_id,
                    "t_start_ms": seg.t_start_ms,
                    "t_end_ms": seg.t_end_ms,
                    "transcript_src": seg.transcript_src,
                    "translation_en": seg.translation_en,
                    "confidence": seg.confidence,
                    "latency_ms": seg.latency_ms,
                    "is_final": seg.finalized,
                }
                for seg in segments
            ],
        }
        return json.dumps(payload, indent=2, ensure_ascii=False)

    def export_csv(self, session_id: str) -> str:
        segments = self.get_segments(session_id)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "segment_id",
                "t_start_ms",
                "t_end_ms",
                "transcript_src",
                "translation_en",
                "confidence",
                "latency_ms",
                "is_final",
            ]
        )
        for seg in segments:
            writer.writerow(
                [
                    seg.segment_id,
                    seg.t_start_ms,
                    seg.t_end_ms,
                    seg.transcript_src,
                    seg.translation_en,
                    f"{seg.confidence:.3f}",
                    seg.latency_ms,
                    "1" if seg.finalized else "0",
                ]
            )
        return output.getvalue()

    def export_srt(self, session_id: str) -> str:
        segments = self.get_segments(session_id)
        lines: list[str] = []
        for idx, seg in enumerate(segments, start=1):
            lines.append(str(idx))
            lines.append(
                f"{_srt_time(seg.t_start_ms)} --> {_srt_time(seg.t_end_ms)}"
            )
            lines.append(seg.translation_en or seg.transcript_src)
            lines.append("")
        return "\n".join(lines)


def _srt_time(ms: int) -> str:
    if ms < 0:
        ms = 0
    hours = ms // 3_600_000
    rem = ms % 3_600_000
    minutes = rem // 60_000
    rem = rem % 60_000
    seconds = rem // 1_000
    millis = rem % 1_000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"