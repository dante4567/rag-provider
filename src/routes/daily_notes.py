"""
Daily Notes API Routes

Endpoints for generating daily/weekly/monthly journal notes
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
from typing import Optional
import logging

from src.core.dependencies import get_rag_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/generate-weekly-note")
async def generate_weekly_note(
    date: Optional[str] = None,
    force: bool = False,
    rag_service = Depends(get_rag_service)
):
    """
    Generate weekly note for the week containing the given date

    Args:
        date: Date string in YYYY-MM-DD format (defaults to today)
        force: Regenerate even if note already exists

    Returns:
        Path to generated weekly note
    """
    try:
        # Parse date
        if date:
            target_date = datetime.strptime(date, '%Y-%m-%d')
        else:
            target_date = datetime.now()

        # Generate weekly note
        await rag_service.daily_note_service.generate_weekly_note(
            date=target_date,
            force_regenerate=force
        )

        year, week = rag_service.daily_note_service.get_week_number(target_date)
        note_path = f"/data/obsidian/refs/weeks/{year}-W{week:02d}.md"

        return {
            "success": True,
            "note_path": note_path,
            "week": f"{year}-W{week:02d}",
            "date": target_date.strftime('%Y-%m-%d')
        }

    except Exception as e:
        logger.error(f"Failed to generate weekly note: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate weekly note: {str(e)}"
        )


@router.post("/generate-monthly-note")
async def generate_monthly_note(
    date: Optional[str] = None,
    force: bool = False,
    rag_service = Depends(get_rag_service)
):
    """
    Generate monthly note for the month containing the given date

    Args:
        date: Date string in YYYY-MM-DD format (defaults to today)
        force: Regenerate even if note already exists

    Returns:
        Path to generated monthly note
    """
    try:
        # Parse date
        if date:
            target_date = datetime.strptime(date, '%Y-%m-%d')
        else:
            target_date = datetime.now()

        # Generate monthly note
        await rag_service.daily_note_service.generate_monthly_note(
            date=target_date,
            force_regenerate=force
        )

        month_str = target_date.strftime('%Y-%m')
        note_path = f"/data/obsidian/refs/months/{month_str}.md"

        return {
            "success": True,
            "note_path": note_path,
            "month": month_str,
            "date": target_date.strftime('%Y-%m-%d')
        }

    except Exception as e:
        logger.error(f"Failed to generate monthly note: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate monthly note: {str(e)}"
        )


@router.get("/daily-note/{date}")
async def get_daily_note(
    date: str,
    rag_service = Depends(get_rag_service)
):
    """
    Get daily note for a specific date

    Args:
        date: Date string in YYYY-MM-DD format

    Returns:
        Daily note content or 404 if not exists
    """
    try:
        target_date = datetime.strptime(date, '%Y-%m-%d')
        note_path = rag_service.daily_note_service.get_daily_note_path(target_date)

        if not note_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Daily note for {date} not found"
            )

        content = note_path.read_text(encoding='utf-8')

        return {
            "success": True,
            "date": date,
            "note_path": str(note_path),
            "content": content
        }

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Use YYYY-MM-DD"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get daily note: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get daily note: {str(e)}"
        )
