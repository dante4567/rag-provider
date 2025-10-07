"""
Monitoring Routes - System drift detection and health monitoring

Provides API endpoints for:
- Capturing drift snapshots
- Detecting drift and anomalies
- Viewing dashboard data
- Alert history
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta

from src.services.drift_monitor_service import DriftMonitorService

router = APIRouter(tags=["monitoring"])

# Global service instance
drift_monitor = DriftMonitorService()


class CaptureSnapshotResponse(BaseModel):
    """Response from snapshot capture"""
    timestamp: str
    total_documents: int
    total_chunks: int
    avg_signalness: float
    duplicate_rate: float


class DriftAlertResponse(BaseModel):
    """Drift alert information"""
    alert_id: str
    timestamp: str
    severity: str
    category: str
    metric: str
    message: str
    deviation_pct: float


@router.post("/monitoring/snapshot", response_model=CaptureSnapshotResponse)
async def capture_snapshot():
    """
    Capture current system state snapshot

    Returns:
        Snapshot with key metrics
    """
    try:
        # Import collection from app
        from app import collection

        snapshot = drift_monitor.capture_snapshot(collection)

        return CaptureSnapshotResponse(
            timestamp=snapshot.timestamp,
            total_documents=snapshot.total_documents,
            total_chunks=snapshot.total_chunks,
            avg_signalness=snapshot.avg_signalness,
            duplicate_rate=snapshot.duplicate_rate
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to capture snapshot: {str(e)}")


@router.get("/monitoring/drift")
async def detect_drift(
    baseline_days_ago: int = 7,
    capture_current: bool = True
):
    """
    Detect drift between current state and baseline

    Args:
        baseline_days_ago: How many days ago to use as baseline (default 7)
        capture_current: Whether to capture a new snapshot or use latest

    Returns:
        Drift alerts and comparison
    """
    try:
        from app import collection

        # Capture current snapshot if requested
        if capture_current:
            current = drift_monitor.capture_snapshot(collection)
        else:
            # Load latest snapshot
            snapshots = drift_monitor.load_snapshots(limit=1)
            if not snapshots:
                raise HTTPException(
                    status_code=400,
                    detail="No snapshots available. Capture a snapshot first."
                )
            current = snapshots[0]

        # Load baseline snapshot
        all_snapshots = drift_monitor.load_snapshots(limit=30)

        if not all_snapshots:
            raise HTTPException(
                status_code=400,
                detail="No baseline snapshots available. Capture snapshots over time first."
            )

        # Find baseline from N days ago
        cutoff = datetime.now() - timedelta(days=baseline_days_ago)
        baseline_candidates = [
            s for s in all_snapshots
            if datetime.fromisoformat(s.timestamp) <= cutoff
        ]

        if not baseline_candidates:
            # Use oldest available
            baseline = all_snapshots[-1]
        else:
            # Use most recent within baseline period
            baseline = baseline_candidates[0]

        # Detect drift
        alerts = drift_monitor.detect_drift(current, baseline)

        # Convert alerts to response format
        alert_responses = []
        for alert in alerts:
            alert_responses.append(DriftAlertResponse(
                alert_id=alert.alert_id,
                timestamp=alert.timestamp,
                severity=alert.severity,
                category=alert.category,
                metric=alert.metric,
                message=alert.message,
                deviation_pct=alert.deviation_pct
            ))

        return {
            "current_timestamp": current.timestamp,
            "baseline_timestamp": baseline.timestamp,
            "days_between": baseline_days_ago,
            "alert_count": len(alert_responses),
            "alerts": alert_responses,
            "metrics": {
                "signalness_change": current.avg_signalness - baseline.avg_signalness,
                "duplicate_rate_change": current.duplicate_rate - baseline.duplicate_rate,
                "document_count_change": current.total_documents - baseline.total_documents
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to detect drift: {str(e)}")


@router.get("/monitoring/dashboard")
async def get_dashboard_data(days: int = 30):
    """
    Get dashboard data for visualization

    Args:
        days: Number of days of history to include (default 30)

    Returns:
        Time series data and current metrics for dashboard
    """
    try:
        dashboard_data = drift_monitor.get_dashboard_data(days=days)

        return dashboard_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard data: {str(e)}")


@router.get("/monitoring/snapshots")
async def list_snapshots(limit: int = 30):
    """
    List recent snapshots

    Args:
        limit: Maximum number of snapshots to return

    Returns:
        List of snapshot summaries
    """
    try:
        snapshots = drift_monitor.load_snapshots(limit=limit)

        snapshot_summaries = []
        for snapshot in snapshots:
            snapshot_summaries.append({
                "timestamp": snapshot.timestamp,
                "total_documents": snapshot.total_documents,
                "avg_signalness": snapshot.avg_signalness,
                "duplicate_rate": snapshot.duplicate_rate,
                "docs_last_24h": snapshot.docs_last_24h
            })

        return {
            "snapshot_count": len(snapshot_summaries),
            "snapshots": snapshot_summaries
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list snapshots: {str(e)}")


@router.get("/monitoring/alerts")
async def list_alerts(limit: int = 50):
    """
    List recent alerts

    Args:
        limit: Maximum number of alerts to return

    Returns:
        List of recent alerts
    """
    try:
        recent_alerts = drift_monitor.alerts[-limit:] if drift_monitor.alerts else []

        alert_responses = []
        for alert in reversed(recent_alerts):
            alert_responses.append({
                "alert_id": alert.alert_id,
                "timestamp": alert.timestamp,
                "severity": alert.severity,
                "category": alert.category,
                "metric": alert.metric,
                "message": alert.message,
                "deviation_pct": alert.deviation_pct
            })

        return {
            "alert_count": len(alert_responses),
            "alerts": alert_responses
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list alerts: {str(e)}")


@router.post("/monitoring/report")
async def generate_drift_report(baseline_days_ago: int = 7):
    """
    Generate comprehensive drift analysis report

    Args:
        baseline_days_ago: How many days ago to use as baseline

    Returns:
        Detailed drift report with recommendations
    """
    try:
        from app import collection

        # Capture current snapshot
        current = drift_monitor.capture_snapshot(collection)

        # Load baseline
        all_snapshots = drift_monitor.load_snapshots(limit=30)

        if not all_snapshots:
            raise HTTPException(
                status_code=400,
                detail="No baseline snapshots available."
            )

        cutoff = datetime.now() - timedelta(days=baseline_days_ago)
        baseline_candidates = [
            s for s in all_snapshots
            if datetime.fromisoformat(s.timestamp) <= cutoff
        ]

        baseline = baseline_candidates[0] if baseline_candidates else all_snapshots[-1]

        # Generate report
        report = drift_monitor.generate_drift_report(
            current,
            baseline,
            baseline_period_desc=f"{baseline_days_ago} days ago",
            current_period_desc="now"
        )

        return {
            "report_id": report.report_id,
            "timestamp": report.timestamp,
            "alert_count": len(report.alerts),
            "critical_alerts": len([a for a in report.alerts if a.severity == "critical"]),
            "warning_alerts": len([a for a in report.alerts if a.severity == "warning"]),
            "trends": report.trends,
            "recommendations": report.recommendations,
            "alerts": [
                {
                    "severity": a.severity,
                    "category": a.category,
                    "message": a.message,
                    "deviation_pct": a.deviation_pct
                }
                for a in report.alerts
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")


@router.post("/monitoring/schedule-snapshot")
async def schedule_snapshot(background_tasks: BackgroundTasks):
    """
    Schedule a snapshot to be captured in the background

    Returns:
        Confirmation that snapshot was scheduled
    """
    try:
        def capture_in_background():
            from app import collection
            drift_monitor.capture_snapshot(collection)

        background_tasks.add_task(capture_in_background)

        return {
            "success": True,
            "message": "Snapshot capture scheduled in background"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to schedule snapshot: {str(e)}")


@router.get("/monitoring/health")
async def monitoring_health():
    """
    Get monitoring system health status

    Returns:
        Health status with snapshot count, alert count, etc.
    """
    try:
        snapshots = drift_monitor.load_snapshots(limit=100)

        # Check if we have recent snapshots
        now = datetime.now()
        recent_snapshots = [
            s for s in snapshots
            if (now - datetime.fromisoformat(s.timestamp)) < timedelta(days=1)
        ]

        return {
            "status": "healthy" if recent_snapshots else "no_recent_snapshots",
            "total_snapshots": len(snapshots),
            "snapshots_last_24h": len(recent_snapshots),
            "total_alerts": len(drift_monitor.alerts),
            "critical_alerts": len([a for a in drift_monitor.alerts if a.severity == "critical"]),
            "snapshots_directory": str(drift_monitor.snapshots_dir)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get health status: {str(e)}")
