"""API routes."""
from __future__ import annotations

import os
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from app.database import get_db, get_database_target
from app.schemas import (
    ProjectInput, AnalyzeResponse,
    DocumentResponse, DocumentAnnotationResponse,
)
from app.scenario_generator import generate_scenarios
from app.models import Incentive, Treaty, Document, DocumentAnnotation, SourceAlert, DataUpdateProposal
from app import countries
from app import llm_intake

DOCUMENTS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "documents")

router = APIRouter()


class IntakeMessageRequest(BaseModel):
    session_id: str
    message: str


class CulturalTestRequest(BaseModel):
    session_id: str
    country_code: str
    country_name: str
    action: str  # "pass", "fail", or "start_review"
    incentive_name: str = ""
    score_info: str = ""


class CulturalTestMessageRequest(BaseModel):
    session_id: str
    country_code: str
    message: str


class DataUpdateProposalRequest(BaseModel):
    incentive_id: int
    field_name: str  # e.g., "rebate_percent", "min_qualifying_spend"
    new_value: str  # String representation (will be converted as needed)
    proposed_source_url: str  # URL to official source
    proposed_source_description: str  # e.g., "Official CNC website, March 2026"
    proposer_email: str  # For follow-up


class DataUpdateProposalResponse(BaseModel):
    id: int
    incentive_id: int
    field_name: str
    old_value: str | None
    new_value: str
    proposed_source_url: str
    status: str
    created_at: str
    reviewed_at: str | None
    reviewed_by: str | None


class ReviewProposalRequest(BaseModel):
    action: str  # "approve" or "reject"
    notes: str | None = None  # Admin review notes



@router.post("/projects/analyze", response_model=AnalyzeResponse)
def analyze_project(project: ProjectInput, db: Session = Depends(get_db)):
    """Analyze project and return financing scenarios."""
    scenarios = generate_scenarios(project, db)

    # Build summary
    format_display = project.format.replace("_", " ").title()
    summary_parts = [f"{format_display}, {project.budget_currency} {project.budget:,.0f}, Stage: {project.stage}."]
    if project.shoot_locations:
        locs = ", ".join(f"{loc.country} {loc.percent}%" for loc in project.shoot_locations)
        summary_parts.append(f"Shoot: {locs}.")

    warnings = []
    if not project.shoot_locations:
        warnings.append("Add shooting locations for more accurate scenarios.")
    else:
        total_pct = sum(loc.percent for loc in project.shoot_locations)
        if abs(total_pct - 100) > 1:
            warnings.append(f"Shoot location percentages sum to {total_pct}%, not 100%. Results may be less accurate.")

    if not scenarios:
        warnings.append("No matching scenarios found. Try adding more countries, adjusting your budget, or enabling flexibility options.")

    return AnalyzeResponse(
        project_summary=" ".join(summary_parts),
        scenarios=scenarios,
        warnings=warnings,
    )


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """Return database stats for the UI header."""
    n_incentives = db.query(Incentive).count()
    n_treaties = db.query(Treaty).count()
    n_countries = db.query(Incentive.country_code).distinct().count()
    return {"countries": n_countries, "incentives": n_incentives, "treaties": n_treaties}


@router.get("/health/db")
def db_health(db: Session = Depends(get_db)):
    """Return database target and readiness counts."""
    n_incentives = db.query(Incentive).count()
    n_treaties = db.query(Treaty).count()
    n_documents = db.query(Document).count()
    n_annotations = db.query(DocumentAnnotation).count()
    return {
        "database_target": get_database_target(),
        "incentives": n_incentives,
        "treaties": n_treaties,
        "documents": n_documents,
        "annotations": n_annotations,
        "ready": n_incentives > 0 and n_treaties > 0,
    }


@router.get("/countries")
def list_countries():
    """Return all known countries for autocomplete."""
    return countries.all_countries()


@router.get("/incentives")
def list_incentives(db: Session = Depends(get_db)):
    """Return all incentives with full provenance."""
    items = db.query(Incentive).order_by(Incentive.country_code, Incentive.name).all()
    return [
        {
            "id": i.id,
            "name": i.name,
            "country_code": i.country_code,
            "country_name": countries.display_name(i.country_code),
            "region": i.region,
            "incentive_type": i.incentive_type,
            "rebate_percent": i.rebate_percent,
            "rebate_applies_to": i.rebate_applies_to,
            "max_cap_amount": i.max_cap_amount,
            "max_cap_currency": i.max_cap_currency,
            "min_total_budget": i.min_total_budget,
            "min_qualifying_spend": i.min_qualifying_spend,
            "eligible_formats": i.eligible_formats,
            "local_producer_required": i.local_producer_required,
            "cultural_test_required": i.cultural_test_required,
            "notes": i.notes,
            "source_url": i.source_url,
            "source_description": i.source_description,
            "clause_reference": getattr(i, 'clause_reference', None),
            "last_verified": i.last_verified,
        }
        for i in items
    ]


@router.post("/intake/start")
def intake_start():
    """Start a new LLM-guided intake session."""
    return llm_intake.start_session()


@router.post("/intake/message")
def intake_message(req: IntakeMessageRequest, db: Session = Depends(get_db)):
    """Send a message in an existing intake session."""
    return llm_intake.send_message(req.session_id, req.message, db=db)



@router.post("/intake/upload")
async def intake_upload(
    session_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a PDF treatment/document for extraction."""
    content = await file.read()
    mime_type = file.content_type or "application/pdf"
    return llm_intake.process_upload(session_id, content, mime_type, db=db)


@router.post("/intake/cultural-test")
def intake_cultural_test(req: CulturalTestRequest):
    """Handle cultural test pass/fail/start_review for a country."""
    return llm_intake.handle_cultural_test(
        req.session_id, req.country_code, req.country_name,
        req.action, req.incentive_name, req.score_info,
    )


@router.post("/intake/cultural-test-message")
def intake_cultural_test_message(req: CulturalTestMessageRequest):
    """Continue an interactive cultural test review conversation."""
    return llm_intake.handle_cultural_test_message(
        req.session_id, req.country_code, req.message,
    )


@router.get("/treaties")
def list_treaties(db: Session = Depends(get_db)):
    """Return all treaties with full provenance."""
    items = db.query(Treaty).filter(Treaty.is_active == True).order_by(Treaty.name).all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "treaty_type": t.treaty_type,
            "country_a_code": t.country_a_code,
            "country_a_name": countries.display_name(t.country_a_code),
            "country_b_code": t.country_b_code,
            "country_b_name": countries.display_name(t.country_b_code) if t.country_b_code else None,
            "min_share_percent": t.min_share_percent,
            "max_share_percent": t.max_share_percent,
            "eligible_formats": t.eligible_formats,
            "creative_requirements": t.creative_requirements_summary,
            "competent_authority_a": t.competent_authority_a,
            "competent_authority_b": t.competent_authority_b,
            "notes": t.notes,
            "source_url": t.source_url,
            "source_description": t.source_description,
        }
        for t in items
    ]


# --- Document / PDF viewer endpoints ---

def _doc_to_response(doc: Document, annotations: list[DocumentAnnotation]) -> dict:
    return {
        "id": doc.id,
        "title": doc.title,
        "document_type": doc.document_type,
        "language": doc.language,
        "country_codes": doc.country_codes or [],
        "page_count": doc.page_count,
        "original_url": doc.original_url,
        "publisher": doc.publisher,
        "annotations": [
            {
                "id": a.id,
                "page_number": a.page_number,
                "search_text": a.search_text,
                "clause_reference": a.clause_reference,
                "topic": a.topic,
                "original_text": a.original_text,
                "english_summary": a.english_summary,
            }
            for a in annotations
        ],
    }


@router.get("/documents")
def list_documents(
    country_code: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """List all documents, optionally filtered by country code."""
    query = db.query(Document)
    if country_code:
        # SQLite JSON: check if the array contains the code
        query = query.filter(Document.country_codes.like(f'%"{country_code}"%'))
    docs = query.order_by(Document.title).all()
    result = []
    for doc in docs:
        anns = (
            db.query(DocumentAnnotation)
            .filter(DocumentAnnotation.document_id == doc.id)
            .order_by(DocumentAnnotation.sort_order, DocumentAnnotation.page_number)
            .all()
        )
        result.append(_doc_to_response(doc, anns))
    return result


@router.get("/documents/{document_id}")
def get_document(document_id: int, db: Session = Depends(get_db)):
    """Get document metadata + all annotations."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    anns = (
        db.query(DocumentAnnotation)
        .filter(DocumentAnnotation.document_id == doc.id)
        .order_by(DocumentAnnotation.sort_order, DocumentAnnotation.page_number)
        .all()
    )
    return _doc_to_response(doc, anns)


@router.get("/documents/{document_id}/file")
def get_document_file(document_id: int, db: Session = Depends(get_db)):
    """Serve the actual PDF file."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    # Look in all subdirectories under DOCUMENTS_DIR
    for root, _dirs, files in os.walk(DOCUMENTS_DIR):
        if doc.filename in files:
            return FileResponse(
                os.path.join(root, doc.filename),
                media_type="application/pdf",
                filename=doc.filename,
            )
    raise HTTPException(404, f"PDF file '{doc.filename}' not found on disk")


@router.get("/documents/by-incentive/{incentive_id}")
def get_documents_for_incentive(incentive_id: int, db: Session = Depends(get_db)):
    """Get documents linked to a specific incentive."""
    docs = db.query(Document).filter(Document.incentive_id == incentive_id).all()
    result = []
    for doc in docs:
        anns = (
            db.query(DocumentAnnotation)
            .filter(DocumentAnnotation.document_id == doc.id)
            .order_by(DocumentAnnotation.sort_order, DocumentAnnotation.page_number)
            .all()
        )
        result.append(_doc_to_response(doc, anns))
    return result


@router.get("/documents/by-treaty/{treaty_id}")
def get_documents_for_treaty(treaty_id: int, db: Session = Depends(get_db)):
    """Get documents linked to a specific treaty."""
    docs = db.query(Document).filter(Document.treaty_id == treaty_id).all()
    result = []
    for doc in docs:
        anns = (
            db.query(DocumentAnnotation)
            .filter(DocumentAnnotation.document_id == doc.id)
            .order_by(DocumentAnnotation.sort_order, DocumentAnnotation.page_number)
            .all()
        )
        result.append(_doc_to_response(doc, anns))
    return result


@router.get("/admin/freshness-status")
def freshness_status(db: Session = Depends(get_db)):
    """Return source freshness summary by status and country."""
    alerts = db.query(SourceAlert).all()

    if not alerts:
        return {
            "total_incentives": 0,
            "green": 0,
            "yellow": 0,
            "red": 0,
            "by_country": {},
            "message": "No freshness data yet. Run: python scripts/check_source_freshness.py",
        }

    # Count by status
    status_counts = {"green": 0, "yellow": 0, "red": 0}
    for alert in alerts:
        if alert.status in status_counts:
            status_counts[alert.status] += 1

    # Group by country
    by_country = {}
    for alert in alerts:
        incentive = db.query(Incentive).filter(Incentive.id == alert.incentive_id).first()
        if incentive:
            cc = incentive.country_code
            if cc not in by_country:
                by_country[cc] = {
                    "country_name": countries.display_name(cc),
                    "green": 0,
                    "yellow": 0,
                    "red": 0,
                    "total": 0,
                }
            by_country[cc][alert.status] += 1
            by_country[cc]["total"] += 1

    total = len(alerts)
    green_pct = round((status_counts["green"] / total) * 100) if total > 0 else 0

    return {
        "total_incentives": total,
        "green": status_counts["green"],
        "yellow": status_counts["yellow"],
        "red": status_counts["red"],
        "green_percent": green_pct,
        "by_country": by_country,
        "last_checked": alerts[0].checked_at if alerts else None,
    }


@router.post("/data/propose-update", response_model=DataUpdateProposalResponse)
def propose_data_update(req: DataUpdateProposalRequest, db: Session = Depends(get_db)):
    """Submit a data correction proposal from a community contributor.

    Filmmakers/professionals can report stale or incorrect incentive data
    and propose updates with official source citations.
    """
    # Fetch the incentive to get old value
    inc = db.query(Incentive).filter(Incentive.id == req.incentive_id).first()
    if not inc:
        raise HTTPException(404, f"Incentive {req.incentive_id} not found")

    # Get current value from the field
    old_value = getattr(inc, req.field_name, None)
    if old_value is None:
        old_value_str = None
    else:
        old_value_str = str(old_value)

    # Create proposal
    proposal = DataUpdateProposal(
        incentive_id=req.incentive_id,
        field_name=req.field_name,
        old_value=old_value_str,
        new_value=req.new_value,
        proposed_source_url=req.proposed_source_url,
        proposed_source_description=req.proposed_source_description,
        proposer_email=req.proposer_email,
        status="pending",
        created_at=datetime.utcnow().isoformat(),
    )
    db.add(proposal)
    db.commit()
    db.refresh(proposal)

    return DataUpdateProposalResponse(
        id=proposal.id,
        incentive_id=proposal.incentive_id,
        field_name=proposal.field_name,
        old_value=proposal.old_value,
        new_value=proposal.new_value,
        proposed_source_url=proposal.proposed_source_url,
        status=proposal.status,
        created_at=proposal.created_at,
        reviewed_at=proposal.reviewed_at,
        reviewed_by=proposal.reviewed_by,
    )


@router.get("/admin/update-proposals")
def list_update_proposals(
    status: str | None = None,
    db: Session = Depends(get_db)
):
    """List all data update proposals (optionally filtered by status).

    Status: 'pending', 'approved', 'rejected' or None for all.
    """
    query = db.query(DataUpdateProposal)
    if status:
        query = query.filter(DataUpdateProposal.status == status)

    proposals = query.order_by(DataUpdateProposal.created_at.desc()).all()

    result = []
    for prop in proposals:
        inc = db.query(Incentive).filter(Incentive.id == prop.incentive_id).first()
        result.append({
            "id": prop.id,
            "incentive_id": prop.incentive_id,
            "incentive_name": inc.name if inc else "Unknown",
            "incentive_country": inc.country_code if inc else "??",
            "field_name": prop.field_name,
            "old_value": prop.old_value,
            "new_value": prop.new_value,
            "proposed_source_url": prop.proposed_source_url,
            "proposed_source_description": prop.proposed_source_description,
            "proposer_email": prop.proposer_email,
            "status": prop.status,
            "created_at": prop.created_at,
            "reviewed_at": prop.reviewed_at,
            "reviewed_by": prop.reviewed_by,
            "notes": prop.notes,
        })

    return result


@router.post("/admin/update-proposals/{proposal_id}/review")
def review_proposal(
    proposal_id: int,
    req: ReviewProposalRequest,
    db: Session = Depends(get_db),
):
    """Review and approve/reject a data update proposal.

    On approval: updates the incentive field and resets last_verified to today.
    """
    proposal = db.query(DataUpdateProposal).filter(
        DataUpdateProposal.id == proposal_id
    ).first()
    if not proposal:
        raise HTTPException(404, f"Proposal {proposal_id} not found")

    if req.action not in ("approve", "reject"):
        raise HTTPException(400, "action must be 'approve' or 'reject'")

    # Get the incentive
    inc = db.query(Incentive).filter(Incentive.id == proposal.incentive_id).first()
    if not inc:
        raise HTTPException(404, f"Incentive {proposal.incentive_id} not found")

    # Mark proposal as reviewed
    proposal.status = "approved" if req.action == "approve" else "rejected"
    proposal.reviewed_at = datetime.utcnow().isoformat()
    proposal.reviewed_by = "admin"  # TODO: get actual admin user from auth context
    proposal.notes = req.notes

    if req.action == "approve":
        # Update the incentive field
        # Parse new_value based on field type
        field_name = proposal.field_name
        new_value = proposal.new_value

        # Try to parse as appropriate type
        if field_name.endswith("_percent") or field_name.endswith("_fraction"):
            new_value = float(new_value)
        elif field_name.endswith("_amount"):
            new_value = float(new_value)
        elif field_name.endswith("_days"):
            new_value = int(new_value)
        # else: keep as string

        setattr(inc, field_name, new_value)
        # Reset verification date to today
        today = datetime.now().date()
        inc.last_verified = today.strftime("%Y-%m")

    db.add(proposal)
    db.add(inc)
    db.commit()

    return {
        "proposal_id": proposal.id,
        "action": req.action,
        "status": proposal.status,
        "reviewed_at": proposal.reviewed_at,
    }
