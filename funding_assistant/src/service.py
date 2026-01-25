from __future__ import annotations

import email
import imaplib
from email.message import Message
from typing import Iterable

from src.config import AppConfig
from src.emailer import build_digest, send_email
from src.llm import LLMClient
from src.pipeline import (
    build_followup_queries,
    load_projects,
    run_discovery,
    select_search_provider,
)
from src.reply_parser import parse_actions
from src.search_providers import SearchResult
from src.storage import (
    fetch_pivot_suggestions,
    fetch_recent_results,
    fetch_result_by_id,
    insert_results,
    record_action,
    utc_now,
)


def run_discovery_and_email(config: AppConfig, project_id: str | None = None) -> None:
    reports = run_discovery(config, project_id=project_id)
    results = []
    pivots = []
    for report in reports:
        results.extend(report.stored_results)
        pivots.extend(report.pivot_suggestions)
    results = sorted(
        results, key=lambda item: (item.score or 0.0), reverse=True
    )[:20]
    pivots = pivots[:10]
    digest = build_digest(results, pivots)
    send_email(config, "Film Funding Digest", digest)


def _get_text_body(message: Message) -> str:
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(part.get_content_charset() or "utf-8", errors="replace")
    payload = message.get_payload(decode=True)
    if payload:
        return payload.decode(message.get_content_charset() or "utf-8", errors="replace")
    return ""


def fetch_unread_emails(config: AppConfig) -> list[tuple[str, str]]:
    if not all([config.imap_host, config.imap_user, config.imap_pass]):
        raise ValueError("IMAP configuration is incomplete.")
    client = imaplib.IMAP4_SSL(config.imap_host)
    try:
        client.login(config.imap_user, config.imap_pass)
        client.select("INBOX")
        status, data = client.search(None, "UNSEEN")
        if status != "OK":
            return []
        emails: list[tuple[str, str]] = []
        for msg_id in data[0].split():
            _, msg_data = client.fetch(msg_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    subject = msg.get("Subject", "")
                    body = _get_text_body(msg)
                    emails.append((subject, body))
            client.store(msg_id, "+FLAGS", "\\Seen")
        return emails
    finally:
        client.logout()


def process_replies(config: AppConfig) -> None:
    emails = fetch_unread_emails(config)
    for subject, body in emails:
        actions = parse_actions(body)
        for action in actions:
            record_action(
                config.db_path,
                action.action,
                {"subject": subject, "result_id": action.result_id},
            )
            handle_reply_action(config, action.action, action.result_id)


def handle_reply_action(config: AppConfig, action: str, result_id: int) -> None:
    result = fetch_result_by_id(config.db_path, result_id)
    if not result:
        send_email(config, "Film Funding Reply", f"Result {result_id} not found.")
        return
    project = get_project_by_id(config, result.project_id)
    llm = LLMClient(config.gemini_api_key, config.gemini_model)

    if action == "details":
        body = f"[RID:{result.id}] {result.title}\n{result.url}\n\n{result.snippet or ''}"
        send_email(config, "Film Funding Details", body)
        return
    if action == "draft":
        draft = llm.draft_application(project, {"title": result.title, "url": result.url})
        send_email(config, "Draft Application", draft.text)
        return
    if action == "pivot":
        pivots = llm.suggest_pivots(project, [{"title": result.title, "url": result.url}])
        body = "\n".join(pivots) if pivots else "No pivot suggestions yet."
        send_email(config, "Pivot Suggestions", body)
        return
    if action == "deeper":
        followup_queries = build_followup_queries(
            [
                SearchResult(
                    title=result.title,
                    url=result.url,
                    snippet=result.snippet,
                    source=result.source,
                )
            ]
        )
        provider = select_search_provider(config)
        followup_items = []
        for query in followup_queries:
            for item in provider.search(query, max_results=config.max_results_per_query):
                followup_items.append(
                    {
                        "project_id": result.project_id,
                        "segment_id": result.segment_id,
                        "angle_type": "followup",
                        "query": query,
                        "title": item.title or "Untitled result",
                        "url": item.url or "",
                        "snippet": item.snippet,
                        "source": item.source,
                        "score": None,
                        "discovered_at": utc_now(),
                        "raw": item.raw or {},
                    }
                )
        stored = insert_results(config.db_path, followup_items)
        pivots = fetch_pivot_suggestions(config.db_path, result.project_id, limit=5)
        digest = build_digest(stored, pivots)
        send_email(config, "Deeper Search Results", digest)


def get_project_by_id(config: AppConfig, project_id: str) -> dict:
    projects = load_projects(config.projects_path)
    for project in projects:
        if project.get("id") == project_id:
            return project
    return {"id": project_id, "title": project_id, "synopsis": ""}


def build_digest_from_db(
    config: AppConfig, project_id: str | None = None, limit: int = 20
) -> str:
    results = fetch_recent_results(config.db_path, project_id, limit=limit)
    pivots = fetch_pivot_suggestions(config.db_path, project_id, limit=10)
    return build_digest(results, pivots)
