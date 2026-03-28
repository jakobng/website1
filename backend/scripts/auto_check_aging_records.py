#!/usr/bin/env python
"""
Layer 3: Automated Aging Record Verification

Scan aging/stale records and use Claude AI to check if values are still current.
Automatically creates DataUpdateProposal records for findings.

Run this weekly to proactively refresh aging data before community reports in.

Usage:
  python scripts/auto_check_aging_records.py [--limit 10]
"""
import os
import sys
from datetime import datetime, timedelta
import json

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from app.database import SessionLocal
from app.models import Incentive, SourceAlert, DataUpdateProposal
from sqlalchemy import text
import anthropic


def get_aging_records(db, limit: int = None):
    """Query aging records (yellow + red status, i.e., >180 days old)."""
    # Get all records with status yellow or red from source_alerts
    aging = db.query(Incentive).join(
        SourceAlert, Incentive.id == SourceAlert.incentive_id
    ).filter(
        SourceAlert.status.in_(["yellow", "red"])
    ).all()

    if limit:
        aging = aging[:limit]

    return aging


def format_incentive_for_verification(incentive) -> str:
    """Format incentive data for Claude to verify."""

    lines = [
        f"Country: {incentive.country_code}",
        f"Name: {incentive.name}",
        f"Type: {incentive.incentive_type}",
        f"Last verified: {incentive.last_verified or 'Never'}",
        "",
        "Current values:",
    ]

    # Add all relevant fields
    if incentive.rebate_percent is not None:
        lines.append(f"  - Rebate %: {incentive.rebate_percent}")
    if incentive.rebate_applies_to:
        lines.append(f"  - Rebate applies to: {incentive.rebate_applies_to}")
    if incentive.max_cap_amount:
        lines.append(f"  - Max cap: {incentive.max_cap_currency} {incentive.max_cap_amount:,.0f}")
    if incentive.min_total_budget:
        lines.append(f"  - Min total budget: {incentive.min_spend_currency or 'EUR'} {incentive.min_total_budget:,.0f}")
    if incentive.min_qualifying_spend:
        lines.append(f"  - Min qualifying spend: {incentive.min_spend_currency or 'EUR'} {incentive.min_qualifying_spend:,.0f}")
    if incentive.min_spend_percent:
        lines.append(f"  - Min spend %: {incentive.min_spend_percent}%")
    if incentive.min_shoot_percent:
        lines.append(f"  - Min shoot %: {incentive.min_shoot_percent}%")
    if incentive.local_crew_min_percent:
        lines.append(f"  - Local crew %: {incentive.local_crew_min_percent}%")
    if incentive.cultural_test_required:
        lines.append(f"  - Cultural test required: Yes (min score: {incentive.cultural_test_min_score})")

    lines.append("")
    lines.append(f"Source URL: {incentive.source_url or 'Not provided'}")
    lines.append(f"Source description: {incentive.source_description or 'Not provided'}")
    lines.append(f"Notes: {incentive.notes or 'None'}")

    return "\n".join(lines)


def verify_with_claude(incentive) -> dict:
    """Use Claude to check if incentive data is still current.

    Returns: {
        'changed': bool,
        'confidence': 'high' | 'medium' | 'low',
        'changes': [{'field': str, 'old': str, 'new': str, 'reason': str}],
        'notes': str,
        'source_url': str | None,
        'raw_response': str
    }
    """

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    incentive_data = format_incentive_for_verification(incentive)

    prompt = f"""You are a film incentive data verification expert. Your job is to check if incentive data is still current.

Here's a film incentive record that was last verified on {incentive.last_verified or 'an unknown date'}:

{incentive_data}

Please check if this data is still accurate:
1. Search your knowledge for {incentive.country_code} film incentive updates after {incentive.last_verified or 'March 2026'}
2. Identify any values that have changed
3. Be honest about your confidence level (high/medium/low)
4. If you found official sources, mention them

Respond in JSON format:
{{
  "changed": boolean,
  "confidence": "high|medium|low",
  "changes": [
    {{"field": "field_name", "old_value": "...", "new_value": "...", "reason": "why it changed"}}
  ],
  "summary": "brief explanation of findings",
  "found_source": "url or description if you found official source, or null"
}}

Only include actual changes you're confident about. When in doubt, say 'no change'.
"""

    try:
        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        response_text = message.content[0].text

        # Try to parse JSON from response
        try:
            # Sometimes Claude wraps JSON in markdown code blocks
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = response_text

            result = json.loads(json_str)
            result['raw_response'] = response_text
            return result
        except json.JSONDecodeError:
            print(f"  [WARN] Could not parse Claude response as JSON")
            return {
                'changed': False,
                'confidence': 'low',
                'changes': [],
                'summary': 'Could not parse AI response',
                'found_source': None,
                'raw_response': response_text
            }

    except anthropic.APIError as e:
        print(f"  [ERROR] Claude API error: {e}")
        return {
            'changed': False,
            'confidence': 'low',
            'changes': [],
            'summary': f'API error: {str(e)}',
            'found_source': None,
            'raw_response': str(e)
        }


def create_proposal_from_change(db, incentive, change: dict, source_url: str, notes: str) -> DataUpdateProposal:
    """Create a DataUpdateProposal record from a detected change."""

    now = datetime.now().isoformat()

    proposal = DataUpdateProposal(
        incentive_id=incentive.id,
        field_name=change['field'],
        old_value=change.get('old_value'),
        new_value=change.get('new_value'),
        proposed_source_url=source_url or incentive.source_url or "https://example.com",
        proposed_source_description=f"Auto-verified by Claude AI on {now[:10]}",
        proposer_email="automated@copro-calculator.local",
        status="pending",
        created_at=now,
        notes=f"Auto-detected change. Reason: {change.get('reason', 'Unknown')}. Original notes: {notes}"
    )

    return proposal


def auto_check_aging():
    """Main: scan aging records and verify with Claude."""
    db = SessionLocal()

    try:
        print("\n[START] Layer 3: Automated Aging Record Verification")
        print(f"Time: {datetime.now().isoformat()}")
        print("-" * 60)

        # Get aging records
        aging_records = get_aging_records(db)
        print(f"\n[INFO] Found {len(aging_records)} aging/stale records to check")

        if not aging_records:
            print("[OK] No aging records. All data is fresh!")
            return

        # Check if API key is set
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("[ERROR] ANTHROPIC_API_KEY not set. Cannot verify records.")
            print("        Set: export ANTHROPIC_API_KEY=sk-...")
            return

        proposals_created = 0
        checked = 0
        errors = 0

        for incentive in aging_records:
            checked += 1
            print(f"\n[{checked}/{len(aging_records)}] {incentive.country_code}: {incentive.name}")

            # Verify with Claude
            result = verify_with_claude(incentive)

            if result.get('changed'):
                print(f"     [FOUND] {len(result.get('changes', []))} change(s) detected")
                print(f"     Confidence: {result.get('confidence')}")

                # Only create proposals for high-confidence changes
                if result.get('confidence') in ['high', 'medium']:
                    for change in result.get('changes', []):
                        proposal = create_proposal_from_change(
                            db,
                            incentive,
                            change,
                            result.get('found_source'),
                            result.get('summary')
                        )
                        db.add(proposal)
                        proposals_created += 1
                        print(f"       -> Created proposal: {change['field']}: {change.get('old_value')} → {change.get('new_value')}")
                else:
                    print(f"     [SKIP] Low confidence, not creating proposal")
            else:
                print(f"     [OK] No changes detected")

        db.commit()

        # Summary
        print("\n" + "-" * 60)
        print(f"[SUCCESS] Verification complete")
        print(f"  Records checked: {checked}")
        print(f"  Proposals created: {proposals_created}")
        print(f"  Next step: Review pending proposals at /admin/update-proposals")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Auto-verify aging incentive records")
    parser.add_argument("--limit", type=int, default=None, help="Limit records to check (for testing)")
    args = parser.parse_args()

    auto_check_aging()
