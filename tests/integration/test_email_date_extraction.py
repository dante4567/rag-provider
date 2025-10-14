"""
Integration tests for email date extraction

Tests that emails are ingested with correct dates from their headers,
not the ingestion timestamp.
"""

import pytest
import os
from datetime import datetime
from pathlib import Path
import tempfile


@pytest.fixture
def test_email_2022():
    """Create test email from 2022"""
    content = """From: test@example.com
To: recipient@example.com
Subject: Test Email from 2022
Date: Tue, 25 Jan 2022 10:09:00 +0000
Message-ID: <test2022@example.com>

This email is from January 25, 2022.
It should appear in daily note for 2022-01-25.
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.eml', delete=False) as f:
        f.write(content)
        return f.name


@pytest.fixture
def test_email_2023():
    """Create test email from 2023"""
    content = """From: sender@test.com
To: you@test.com
Subject: Meeting Notes
Date: Wed, 15 Mar 2023 14:30:00 +0000
Message-ID: <test2023@example.com>

Meeting notes from March 2023.
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.eml', delete=False) as f:
        f.write(content)
        return f.name


@pytest.mark.integration
def test_email_date_extraction_2022(client, test_email_2022, obsidian_vault_path):
    """Test that email from 2022 gets correct date"""
    # Ingest email
    with open(test_email_2022, 'rb') as f:
        response = client.post(
            "/ingest/file",
            files={"file": ("test_2022.eml", f, "message/rfc822")},
            data={"generate_obsidian": "true"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

    # Check Obsidian filename has correct date
    obsidian_path = data["obsidian_path"]
    assert "2022-01-25" in obsidian_path, f"Expected 2022-01-25 in path, got: {obsidian_path}"

    # Check metadata has correct created_at
    created_at = data["metadata"]["created_at"]
    assert created_at.startswith("2022-01-25"), f"Expected 2022-01-25, got: {created_at}"

    # Check daily note was created for 2022-01-25
    daily_note_path = Path(obsidian_vault_path) / "refs" / "days" / "2022-01-25.md"
    assert daily_note_path.exists(), f"Daily note not created: {daily_note_path}"

    # Verify email appears in daily note
    daily_note_content = daily_note_path.read_text()
    assert "test email from 2022" in daily_note_content.lower()

    # Cleanup
    os.unlink(test_email_2022)


@pytest.mark.integration
def test_email_date_extraction_2023(client, test_email_2023, obsidian_vault_path):
    """Test that email from 2023 gets correct date"""
    # Ingest email
    with open(test_email_2023, 'rb') as f:
        response = client.post(
            "/ingest/file",
            files={"file": ("test_2023.eml", f, "message/rfc822")},
            data={"generate_obsidian": "true"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

    # Check Obsidian filename has correct date
    obsidian_path = data["obsidian_path"]
    assert "2023-03-15" in obsidian_path, f"Expected 2023-03-15 in path, got: {obsidian_path}"

    # Check metadata has correct created_at
    created_at = data["metadata"]["created_at"]
    assert created_at.startswith("2023-03-15"), f"Expected 2023-03-15, got: {created_at}"

    # Check daily note was created for 2023-03-15
    daily_note_path = Path(obsidian_vault_path) / "refs" / "days" / "2023-03-15.md"
    assert daily_note_path.exists(), f"Daily note not created: {daily_note_path}"

    # Verify email appears in daily note
    daily_note_content = daily_note_path.read_text()
    assert "meeting notes" in daily_note_content.lower()

    # Cleanup
    os.unlink(test_email_2023)


@pytest.mark.integration
def test_email_not_in_todays_daily_note(client, test_email_2022, obsidian_vault_path):
    """Verify old email does NOT appear in today's daily note"""
    # Ingest email from 2022
    with open(test_email_2022, 'rb') as f:
        response = client.post(
            "/ingest/file",
            files={"file": ("test_2022.eml", f, "message/rfc822")},
            data={"generate_obsidian": "true"}
        )

    assert response.status_code == 200

    # Check that today's daily note doesn't contain this email
    today = datetime.now().strftime("%Y-%m-%d")
    today_note_path = Path(obsidian_vault_path) / "refs" / "days" / f"{today}.md"

    if today_note_path.exists():
        today_content = today_note_path.read_text()
        # The 2022 email should NOT be in today's note
        assert "test email from 2022" not in today_content.lower(), \
            f"Email from 2022 incorrectly appeared in today's daily note ({today})"

    # Cleanup
    os.unlink(test_email_2022)


@pytest.mark.integration
def test_multiple_emails_same_day(client, obsidian_vault_path):
    """Test that multiple emails on same date all appear in same daily note"""
    emails = []

    # Create 3 emails from same date
    for i in range(3):
        content = f"""From: sender{i}@test.com
To: recipient@test.com
Subject: Email {i+1}
Date: Mon, 1 Jan 2024 {10+i}:00:00 +0000
Message-ID: <test{i}@example.com>

Content of email {i+1} from January 1, 2024.
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.eml', delete=False) as f:
            f.write(content)
            emails.append(f.name)

    # Ingest all 3 emails
    doc_ids = []
    for email_file in emails:
        with open(email_file, 'rb') as f:
            response = client.post(
                "/ingest/file",
                files={"file": (os.path.basename(email_file), f, "message/rfc822")},
                data={"generate_obsidian": "true"}
            )
            assert response.status_code == 200
            doc_ids.append(response.json()["doc_id"])

    # Check daily note contains all 3 emails
    daily_note_path = Path(obsidian_vault_path) / "refs" / "days" / "2024-01-01.md"
    assert daily_note_path.exists()

    daily_note_content = daily_note_path.read_text()
    for i in range(3):
        assert f"email {i+1}" in daily_note_content.lower(), \
            f"Email {i+1} not found in daily note"

    # Cleanup
    for email_file in emails:
        os.unlink(email_file)
