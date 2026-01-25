#!/usr/bin/env python3
"""
Automated script for GitHub Actions.
Generates digest and sends it via email.
"""

import sys
from datetime import datetime
from pathlib import Path

import yaml

from src.config import AppConfig
from src.digest import generate_digest
from src.emailer import send_email


def load_projects(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("projects", [])


def main() -> int:
    print("=" * 60)
    print("AUTOMATED FUNDING DISCOVERY")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 60)
    
    config = AppConfig()
    
    # Load projects
    projects_path = Path("data/projects.yml")
    if not projects_path.exists():
        print(f"Error: Projects file not found: {projects_path}")
        return 1
    
    projects = load_projects(projects_path)
    print(f"Found {len(projects)} projects")
    
    # Generate digest
    print("\nGenerating digest...")
    try:
        digest_text = generate_digest(
            config=config,
            projects=projects,
            mark_shown=True,  # Mark results as shown for next run
            min_score=0.5,
            max_grants_per_project=20,
            max_orgs_per_project=10,
        )
    except Exception as e:
        print(f"Error generating digest: {e}")
        return 1
    
    # Save digest to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    digest_path = Path(f"data/digest_{timestamp}.txt")
    digest_path.write_text(digest_text, encoding="utf-8")
    print(f"Digest saved to: {digest_path}")
    
    # Send email
    if config.smtp_host and config.to_email:
        print(f"\nSending email to {config.to_email}...")
        try:
            subject = f"Funding Discovery Digest - {datetime.now().strftime('%B %d, %Y')}"
            send_email(config, subject, digest_text)
            print("Email sent successfully!")
        except Exception as e:
            print(f"Error sending email: {e}")
            # Don't fail the whole job if email fails
            print("Continuing without email...")
    else:
        print("\nEmail not configured - skipping email send")
        print("Set SMTP_HOST, SMTP_USER, SMTP_PASS, FROM_EMAIL, TO_EMAIL to enable")
    
    print("\n" + "=" * 60)
    print("AUTOMATED RUN COMPLETE")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
