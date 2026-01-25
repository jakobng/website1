from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


@dataclass
class StoredResult:
    id: int
    project_id: str
    segment_id: str | None
    angle_type: str
    query: str
    title: str
    url: str
    snippet: str | None
    source: str | None
    score: float | None
    discovered_at: str
    # Rich analysis fields
    deadline: str | None = None
    grant_amount: str | None = None
    is_open: str | None = None  # "true", "false", "unknown"
    eligibility_notes: str | None = None
    topic_match: str | None = None  # JSON array as string
    funder_type: str | None = None
    contact_info: str | None = None
    summary: str | None = None
    # Funder tracking
    funder_id: int | None = None
    is_new_funder: bool = False
    # Digest tracking
    shown_in_digest: str | None = None  # ISO timestamp when shown
    result_type: str | None = None  # specific_grant, funder_org, aggregator, news, irrelevant


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS search_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                segment_id TEXT,
                angle_type TEXT NOT NULL,
                query TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                snippet TEXT,
                source TEXT,
                score REAL,
                discovered_at TEXT NOT NULL,
                raw_json TEXT,
                deadline TEXT,
                grant_amount TEXT,
                is_open TEXT,
                eligibility_notes TEXT,
                topic_match TEXT,
                funder_type TEXT,
                contact_info TEXT,
                summary TEXT,
                funder_id INTEGER,
                UNIQUE(project_id, url)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pivot_suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                segment_id TEXT,
                suggestion TEXT NOT NULL,
                source_result_id INTEGER,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS action_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS funders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT NOT NULL UNIQUE,
                name TEXT,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                times_seen INTEGER DEFAULT 1,
                contact_info TEXT
            )
            """
        )
        # Add new columns to existing tables if they don't exist
        _add_column_if_missing(conn, "search_results", "deadline", "TEXT")
        _add_column_if_missing(conn, "search_results", "grant_amount", "TEXT")
        _add_column_if_missing(conn, "search_results", "is_open", "TEXT")
        _add_column_if_missing(conn, "search_results", "eligibility_notes", "TEXT")
        _add_column_if_missing(conn, "search_results", "topic_match", "TEXT")
        _add_column_if_missing(conn, "search_results", "funder_type", "TEXT")
        _add_column_if_missing(conn, "search_results", "contact_info", "TEXT")
        _add_column_if_missing(conn, "search_results", "summary", "TEXT")
        _add_column_if_missing(conn, "search_results", "funder_id", "INTEGER")
        _add_column_if_missing(conn, "search_results", "shown_in_digest", "TEXT")
        _add_column_if_missing(conn, "search_results", "result_type", "TEXT")


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, col_type: str) -> None:
    """Add a column to a table if it doesn't already exist."""
    cursor = conn.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def _extract_domain(url: str) -> str:
    """Extract domain from URL for funder tracking."""
    if "://" in url:
        url = url.split("://", 1)[1]
    domain = url.split("/")[0]
    # Remove www. prefix
    if domain.startswith("www."):
        domain = domain[4:]
    return domain.lower()


def get_or_create_funder(conn: sqlite3.Connection, url: str, name: str | None = None) -> tuple[int, bool]:
    """Get or create a funder record. Returns (funder_id, is_new)."""
    domain = _extract_domain(url)
    if not domain:
        return (0, False)
    
    row = conn.execute(
        "SELECT id, times_seen FROM funders WHERE domain = ?",
        (domain,),
    ).fetchone()
    
    if row:
        # Existing funder - update last_seen and increment count
        conn.execute(
            "UPDATE funders SET last_seen = ?, times_seen = times_seen + 1 WHERE id = ?",
            (utc_now(), row[0]),
        )
        return (row[0], False)
    else:
        # New funder
        cursor = conn.execute(
            """
            INSERT INTO funders (domain, name, first_seen, last_seen, times_seen)
            VALUES (?, ?, ?, ?, 1)
            """,
            (domain, name or domain, utc_now(), utc_now()),
        )
        return (cursor.lastrowid, True)


def insert_results(
    db_path: Path,
    results: Iterable[dict[str, Any]],
) -> list[StoredResult]:
    stored: list[StoredResult] = []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        for result in results:
            # Track funder
            funder_id, is_new_funder = get_or_create_funder(
                conn, result["url"], result.get("title")
            )
            
            payload = json.dumps(result.get("raw", {}), ensure_ascii=True)
            # Convert topic_match list to JSON string if needed
            topic_match = result.get("topic_match")
            if isinstance(topic_match, list):
                topic_match = json.dumps(topic_match)
            
            conn.execute(
                """
                INSERT OR IGNORE INTO search_results
                (project_id, segment_id, angle_type, query, title, url, snippet, source, score, 
                 discovered_at, raw_json, deadline, grant_amount, is_open, eligibility_notes,
                 topic_match, funder_type, contact_info, summary, funder_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result["project_id"],
                    result.get("segment_id"),
                    result["angle_type"],
                    result["query"],
                    result["title"],
                    result["url"],
                    result.get("snippet"),
                    result.get("source"),
                    result.get("score"),
                    result.get("discovered_at", utc_now()),
                    payload,
                    result.get("deadline"),
                    result.get("grant_amount"),
                    str(result.get("is_open", "unknown")),
                    result.get("eligibility_notes"),
                    topic_match,
                    result.get("funder_type"),
                    result.get("contact_info"),
                    result.get("summary"),
                    funder_id if funder_id else None,
                ),
            )
            row = conn.execute(
                """
                SELECT * FROM search_results
                WHERE project_id = ? AND url = ?
                """,
                (result["project_id"], result["url"]),
            ).fetchone()
            if row:
                result_obj = _row_to_stored_result(row)
                result_obj.is_new_funder = is_new_funder
                stored.append(result_obj)
    return stored


def insert_pivot_suggestions(
    db_path: Path,
    suggestions: Iterable[dict[str, Any]],
) -> None:
    with sqlite3.connect(db_path) as conn:
        for suggestion in suggestions:
            conn.execute(
                """
                INSERT INTO pivot_suggestions
                (project_id, segment_id, suggestion, source_result_id, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    suggestion["project_id"],
                    suggestion.get("segment_id"),
                    suggestion["suggestion"],
                    suggestion.get("source_result_id"),
                    suggestion.get("created_at", utc_now()),
                ),
            )


def record_action(db_path: Path, action_type: str, payload: dict[str, Any]) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO action_history (action_type, payload, status, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (action_type, json.dumps(payload, ensure_ascii=True), "queued", utc_now()),
        )


def fetch_recent_results(db_path: Path, project_id: str | None, limit: int = 50) -> list[StoredResult]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        if project_id:
            rows = conn.execute(
                """
                SELECT * FROM search_results
                WHERE project_id = ?
                ORDER BY discovered_at DESC
                LIMIT ?
                """,
                (project_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM search_results
                ORDER BY discovered_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    return [_row_to_stored_result(row) for row in rows]


def _row_to_stored_result(row: sqlite3.Row) -> StoredResult:
    """Convert a database row to a StoredResult, handling missing columns."""
    keys = row.keys()
    return StoredResult(
        id=row["id"],
        project_id=row["project_id"],
        segment_id=row["segment_id"],
        angle_type=row["angle_type"],
        query=row["query"],
        title=row["title"],
        url=row["url"],
        snippet=row["snippet"],
        source=row["source"],
        score=row["score"],
        discovered_at=row["discovered_at"],
        deadline=row["deadline"] if "deadline" in keys else None,
        grant_amount=row["grant_amount"] if "grant_amount" in keys else None,
        is_open=row["is_open"] if "is_open" in keys else None,
        eligibility_notes=row["eligibility_notes"] if "eligibility_notes" in keys else None,
        topic_match=row["topic_match"] if "topic_match" in keys else None,
        funder_type=row["funder_type"] if "funder_type" in keys else None,
        contact_info=row["contact_info"] if "contact_info" in keys else None,
        summary=row["summary"] if "summary" in keys else None,
        funder_id=row["funder_id"] if "funder_id" in keys else None,
        shown_in_digest=row["shown_in_digest"] if "shown_in_digest" in keys else None,
        result_type=row["result_type"] if "result_type" in keys else None,
    )


def fetch_pivot_suggestions(db_path: Path, project_id: str | None, limit: int = 20) -> list[dict[str, Any]]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        if project_id:
            rows = conn.execute(
                """
                SELECT * FROM pivot_suggestions
                WHERE project_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (project_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM pivot_suggestions
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    return [dict(row) for row in rows]


def fetch_result_by_id(db_path: Path, result_id: int) -> StoredResult | None:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM search_results WHERE id = ?",
            (result_id,),
        ).fetchone()
    if not row:
        return None
    return _row_to_stored_result(row)


def get_funder_stats(db_path: Path) -> list[dict[str, Any]]:
    """Get statistics about known funders."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT * FROM funders
            ORDER BY times_seen DESC, last_seen DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def update_funder_contact(db_path: Path, funder_id: int, contact_info: str) -> None:
    """Update contact info for a funder."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE funders SET contact_info = ? WHERE id = ?",
            (contact_info, funder_id),
        )


def fetch_results_for_digest(
    db_path: Path, 
    project_id: str | None = None,
    min_score: float = 0.5,
    include_shown: bool = True,
) -> list[StoredResult]:
    """Fetch results suitable for digest, prioritizing unseen results."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        
        query = """
            SELECT * FROM search_results
            WHERE score >= ?
        """
        params: list = [min_score]
        
        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)
        
        if not include_shown:
            query += " AND shown_in_digest IS NULL"
        
        # Prioritize: unseen first, then by score
        query += """
            ORDER BY 
                CASE WHEN shown_in_digest IS NULL THEN 0 ELSE 1 END,
                score DESC
        """
        
        rows = conn.execute(query, params).fetchall()
    
    return [_row_to_stored_result(row) for row in rows]


def mark_results_shown(db_path: Path, result_ids: list[int]) -> None:
    """Mark results as shown in a digest."""
    if not result_ids:
        return
    with sqlite3.connect(db_path) as conn:
        placeholders = ",".join("?" * len(result_ids))
        conn.execute(
            f"""
            UPDATE search_results 
            SET shown_in_digest = ?
            WHERE id IN ({placeholders})
            """,
            [utc_now()] + result_ids,
        )


def update_result_type(db_path: Path, result_id: int, result_type: str) -> None:
    """Update the result_type classification for a result."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE search_results SET result_type = ? WHERE id = ?",
            (result_type, result_id),
        )
