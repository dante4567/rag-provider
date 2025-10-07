"""
Email Threading Routes - Process and thread email messages

Provides API endpoints for:
- Processing mailbox directories
- Creating threads from email files
- Retrieving thread statistics
"""

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional
import tempfile
import shutil
from pathlib import Path

from src.services.email_threading_service import EmailThreadingService, EmailThread

router = APIRouter(tags=["email-threading"])


class ThreadEmailsRequest(BaseModel):
    """Request to thread emails from a list of file paths"""
    email_files: List[str]


class ThreadEmailsResponse(BaseModel):
    """Response with created threads"""
    thread_count: int
    message_count: int
    threads: List[dict]


class ThreadStatistics(BaseModel):
    """Thread statistics"""
    total_threads: int
    total_messages: int
    avg_messages_per_thread: float
    total_participants: int


@router.post("/threads/process-mailbox")
async def process_mailbox(mailbox_path: str, output_dir: Optional[str] = None):
    """
    Process all emails in a mailbox directory and generate thread MDs

    Args:
        mailbox_path: Path to directory containing .eml files
        output_dir: Optional output directory (defaults to ./email_threads/)

    Returns:
        Statistics about processed threads
    """
    try:
        service = EmailThreadingService()

        if output_dir is None:
            output_dir = "./email_threads"

        threads_created, messages_processed = service.process_mailbox(
            mailbox_path,
            output_dir
        )

        return {
            "success": True,
            "threads_created": threads_created,
            "messages_processed": messages_processed,
            "output_directory": output_dir
        }

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Mailbox not found: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process mailbox: {str(e)}")


@router.post("/threads/create", response_model=ThreadEmailsResponse)
async def create_threads_from_files(email_files: List[UploadFile] = File(...)):
    """
    Upload email files and create threads

    Args:
        email_files: List of .eml email files

    Returns:
        Created threads with metadata
    """
    try:
        service = EmailThreadingService()
        messages = []

        # Create temp directory for uploaded files
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Save uploaded files
            for email_file in email_files:
                file_path = temp_path / email_file.filename
                with open(file_path, 'wb') as f:
                    shutil.copyfileobj(email_file.file, f)

                # Parse email
                message = service.parse_email_file(str(file_path))
                if message:
                    messages.append(message)

            if not messages:
                raise HTTPException(status_code=400, detail="No valid email messages found")

            # Build threads
            threads = service.build_threads(messages)

            # Convert to response format
            thread_dicts = []
            for thread in threads:
                thread_dicts.append({
                    "thread_id": thread.thread_id,
                    "subject": thread.subject,
                    "participants": list(thread.participants),
                    "message_count": thread.message_count,
                    "start_date": thread.start_date.isoformat(),
                    "end_date": thread.end_date.isoformat(),
                    "has_attachments": thread.has_attachments
                })

            return ThreadEmailsResponse(
                thread_count=len(threads),
                message_count=len(messages),
                threads=thread_dicts
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create threads: {str(e)}")


@router.post("/threads/statistics")
async def get_thread_statistics(request: ThreadEmailsRequest):
    """
    Get statistics about email threads

    Args:
        request: List of email file paths

    Returns:
        Thread statistics
    """
    try:
        service = EmailThreadingService()
        messages = []

        for file_path in request.email_files:
            message = service.parse_email_file(file_path)
            if message:
                messages.append(message)

        if not messages:
            raise HTTPException(status_code=400, detail="No valid email messages found")

        threads = service.build_threads(messages)
        stats = service.get_thread_statistics(threads)

        return stats

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")


@router.get("/threads/example")
async def get_example_thread():
    """
    Get an example of thread markdown format

    Returns:
        Example thread markdown with YAML frontmatter
    """
    example = """---
id: msg1
source: email
doc_type: correspondence.thread
title: "Example Email Thread"
created_at: 2025-10-07T10:00:00
ingested_at: 2025-10-07T10:00:00

people: ["alice@example.com", "bob@example.com"]
places: []
projects: []
topics: []

entities:
  orgs: []
  dates: ["2025-10-07"]
  numbers: []

summary: "Email thread: Example Email Thread (2 messages from 2025-10-07 to 2025-10-07)"

# Scoring
quality_score: 1.0
novelty_score: 0.0
actionability_score: 0.0
signalness: 0.0
do_index: false

# Thread metadata
thread:
  message_count: 2
  participants: ["alice@example.com", "bob@example.com"]
  has_attachments: false
  date_range:
    start: 2025-10-07T10:00:00
    end: 2025-10-07T11:00:00

provenance:
  sha256: ""
  mailbox: ""
  message_ids: ["<msg1@example.com>", "<msg2@example.com>"]
enrichment_version: v2.1
---

# Example Email Thread

**Thread:** 2 messages from 2025-10-07 to 2025-10-07

**Participants:** alice@example.com, bob@example.com

---

## Messages

### Message 1: alice@example.com (2025-10-07 10:00)

**To:** bob@example.com

Can we meet tomorrow at 10am?

---

### Message 2: bob@example.com (2025-10-07 11:00)

**To:** alice@example.com

Yes, that works for me.

---
"""

    return {
        "format": "markdown_with_yaml_frontmatter",
        "example": example
    }
