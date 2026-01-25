from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Iterable

from src.config import AppConfig
from src.storage import StoredResult


def format_result_line(result: StoredResult) -> str:
    score = f"{result.score:.2f}" if result.score is not None else "n/a"
    
    # Build status tags
    tags = []
    if getattr(result, "is_new_funder", False):
        tags.append("NEW")
    if getattr(result, "is_open", None) == "true":
        tags.append("OPEN")
    elif getattr(result, "is_open", None) == "false":
        tags.append("CLOSED")
    if getattr(result, "funder_type", None):
        tags.append(result.funder_type.upper())
    
    tag_str = f" [{', '.join(tags)}]" if tags else ""
    
    lines = [f"[RID:{result.id}] {result.title} (score: {score}){tag_str}"]
    lines.append(f"  URL: {result.url}")
    
    # Summary
    if getattr(result, "summary", None):
        lines.append(f"  {result.summary}")
    
    # Key details in a compact format
    details = []
    if getattr(result, "grant_amount", None):
        details.append(f"Amount: {result.grant_amount}")
    if result.deadline:
        details.append(f"Deadline: {result.deadline}")
    if details:
        lines.append(f"  {' | '.join(details)}")
    
    # Eligibility
    if getattr(result, "eligibility_notes", None):
        lines.append(f"  Eligibility: {result.eligibility_notes}")
    
    # Topic match
    if getattr(result, "topic_match", None):
        topic_str = result.topic_match
        if isinstance(topic_str, str) and topic_str.startswith("["):
            import json
            try:
                topics = json.loads(topic_str)
                topic_str = ", ".join(topics)
            except:
                pass
        lines.append(f"  Topics: {topic_str}")
    
    # Contact
    if result.contact_info:
        lines.append(f"  Contact: {result.contact_info}")
    
    return "\n".join(lines)


def format_pivot_line(pivot: dict) -> str:
    return f"[PIVOT] {pivot.get('suggestion')}"


def build_digest(results: Iterable[StoredResult], pivots: Iterable[dict]) -> str:
    results_list = list(results)
    
    # Separate open vs other results
    open_results = [r for r in results_list if getattr(r, "is_open", None) == "true"]
    other_results = [r for r in results_list if getattr(r, "is_open", None) != "true"]
    
    sections = []
    
    # Header
    sections.append("=" * 60)
    sections.append("FILM FUNDING DIGEST")
    sections.append("=" * 60)
    
    # Open opportunities first
    if open_results:
        sections.append("\n📌 CURRENTLY OPEN OPPORTUNITIES")
        sections.append("-" * 40)
        sections.append("\n\n".join(format_result_line(r) for r in open_results))
    
    # Other results
    if other_results:
        sections.append("\n\n📋 OTHER RESULTS")
        sections.append("-" * 40)
        sections.append("\n\n".join(format_result_line(r) for r in other_results))
    
    if not results_list:
        sections.append("\nNo results found.")
    
    # Pivot suggestions
    pivots_list = list(pivots)
    if pivots_list:
        sections.append("\n\n💡 PIVOT SUGGESTIONS")
        sections.append("-" * 40)
        sections.append("\n".join(format_pivot_line(pivot) for pivot in pivots_list))
    
    # Instructions
    sections.append("\n" + "-" * 60)
    sections.append("Commands: deeper <RID> | details <RID> | draft <RID> | pivot <RID>")
    sections.append("=" * 60)
    
    return "\n".join(sections)


def send_email(config: AppConfig, subject: str, body: str) -> None:
    if not all([config.smtp_host, config.smtp_user, config.smtp_pass, config.to_email, config.from_email]):
        raise ValueError("SMTP configuration is incomplete.")
    message = EmailMessage()
    message["From"] = config.from_email
    message["To"] = config.to_email
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(config.smtp_host, config.smtp_port) as server:
        server.starttls()
        server.login(config.smtp_user, config.smtp_pass)
        server.send_message(message)
