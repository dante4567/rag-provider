"""
Drift Monitor Service - Track system behavior changes over time

Implements blueprint requirement: "Monitor domain/signalness/dupe drift,
alert on anomalies"

Features:
- Domain drift detection (content type changes)
- Signalness drift (quality score trends)
- Duplicate rate tracking
- Ingestion pattern monitoring
- Anomaly detection
- Dashboard data generation
"""

import json
import logging
from typing import List, Dict, Set, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field, asdict
from collections import defaultdict, Counter
import statistics

logger = logging.getLogger(__name__)


@dataclass
class DriftSnapshot:
    """Single point-in-time snapshot of system metrics"""
    timestamp: str
    total_documents: int
    total_chunks: int

    # Domain metrics
    doc_types: Dict[str, int]  # e.g., {"pdf": 150, "word": 50}
    sources: Dict[str, int]  # e.g., {"email": 100, "upload": 50}
    topics: Dict[str, int]  # Top topics distribution

    # Quality metrics
    avg_signalness: float
    avg_quality_score: float
    avg_novelty_score: float
    avg_actionability_score: float

    # Deduplication metrics
    duplicate_count: int
    duplicate_rate: float  # Duplicates / total documents

    # Ingestion metrics
    docs_last_24h: int
    docs_last_7d: int
    docs_last_30d: int

    # Storage metrics
    total_storage_mb: float
    avg_doc_size_kb: float


@dataclass
class DriftAlert:
    """Anomaly or drift alert"""
    alert_id: str
    timestamp: str
    severity: str  # "info", "warning", "critical"
    category: str  # "domain", "quality", "duplicates", "ingestion"
    metric: str
    message: str
    current_value: float
    baseline_value: float
    threshold: float
    deviation_pct: float


@dataclass
class DriftReport:
    """Comprehensive drift analysis report"""
    report_id: str
    timestamp: str
    baseline_period: str  # e.g., "2025-01-01 to 2025-01-07"
    current_period: str

    current_snapshot: DriftSnapshot
    baseline_snapshot: DriftSnapshot

    alerts: List[DriftAlert] = field(default_factory=list)
    trends: Dict[str, str] = field(default_factory=dict)  # "increasing", "decreasing", "stable"
    recommendations: List[str] = field(default_factory=list)


class DriftMonitorService:
    """Service for monitoring and detecting system behavior drift"""

    def __init__(self, snapshots_dir: str = "monitoring/drift_snapshots"):
        """
        Initialize drift monitor service

        Args:
            snapshots_dir: Directory to store drift snapshots
        """
        self.snapshots_dir = Path(snapshots_dir)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

        self.snapshots: List[DriftSnapshot] = []
        self.alerts: List[DriftAlert] = []

        # Thresholds for anomaly detection
        self.thresholds = {
            'signalness_drop': 0.15,  # Alert if signalness drops >15%
            'quality_drop': 0.15,
            'duplicate_rate_increase': 0.10,  # Alert if dup rate increases >10%
            'ingestion_spike': 3.0,  # Alert if ingestion >3x baseline
            'topic_shift': 0.25  # Alert if topic distribution changes >25%
        }

    def capture_snapshot(
        self,
        collection,
        metadata_dict: Optional[Dict] = None
    ) -> DriftSnapshot:
        """
        Capture current system state snapshot

        Args:
            collection: ChromaDB collection
            metadata_dict: Optional pre-computed metadata

        Returns:
            DriftSnapshot object
        """
        try:
            # Get collection data
            all_results = collection.get()

            total_documents = len(all_results['ids']) if all_results['ids'] else 0
            metadatas = all_results.get('metadatas', [])

            if not metadatas:
                # Return empty snapshot
                return DriftSnapshot(
                    timestamp=datetime.now().isoformat(),
                    total_documents=0,
                    total_chunks=0,
                    doc_types={},
                    sources={},
                    topics={},
                    avg_signalness=0.0,
                    avg_quality_score=0.0,
                    avg_novelty_score=0.0,
                    avg_actionability_score=0.0,
                    duplicate_count=0,
                    duplicate_rate=0.0,
                    docs_last_24h=0,
                    docs_last_7d=0,
                    docs_last_30d=0,
                    total_storage_mb=0.0,
                    avg_doc_size_kb=0.0
                )

            # Extract metrics
            doc_types = Counter()
            sources = Counter()
            topics = Counter()

            signalness_scores = []
            quality_scores = []
            novelty_scores = []
            actionability_scores = []

            content_hashes = set()
            duplicates = 0

            doc_sizes = []

            now = datetime.now()
            docs_24h = docs_7d = docs_30d = 0

            unique_doc_ids = set()

            for metadata in metadatas:
                # Track unique documents (not chunks)
                doc_id = metadata.get('document_id', '')
                if doc_id:
                    unique_doc_ids.add(doc_id)

                # Doc types
                file_type = metadata.get('file_type', 'unknown')
                doc_types[file_type] += 1

                # Sources
                source = metadata.get('source', 'unknown')
                sources[source] += 1

                # Topics
                doc_topics = metadata.get('topics', [])
                if isinstance(doc_topics, list):
                    for topic in doc_topics:
                        topics[topic] += 1

                # Scores
                signalness = metadata.get('signalness', 0.0)
                if signalness > 0:
                    signalness_scores.append(signalness)

                quality = metadata.get('quality_score', 0.0)
                if quality > 0:
                    quality_scores.append(quality)

                novelty = metadata.get('novelty_score', 0.0)
                if novelty > 0:
                    novelty_scores.append(novelty)

                actionability = metadata.get('actionability_score', 0.0)
                if actionability > 0:
                    actionability_scores.append(actionability)

                # Duplicates
                content_hash = metadata.get('content_hash', '')
                if content_hash:
                    if content_hash in content_hashes:
                        duplicates += 1
                    content_hashes.add(content_hash)

                # Ingestion timing
                ingested_at = metadata.get('ingested_at', '')
                if ingested_at:
                    try:
                        ingested_date = datetime.fromisoformat(ingested_at.replace('Z', '+00:00'))
                        delta = now - ingested_date.replace(tzinfo=None)

                        if delta < timedelta(days=1):
                            docs_24h += 1
                        if delta < timedelta(days=7):
                            docs_7d += 1
                        if delta < timedelta(days=30):
                            docs_30d += 1
                    except Exception:
                        pass

                # Doc sizes
                doc_size = metadata.get('file_size_bytes', 0)
                if doc_size > 0:
                    doc_sizes.append(doc_size)

            # Calculate averages
            avg_signalness = statistics.mean(signalness_scores) if signalness_scores else 0.0
            avg_quality = statistics.mean(quality_scores) if quality_scores else 0.0
            avg_novelty = statistics.mean(novelty_scores) if novelty_scores else 0.0
            avg_actionability = statistics.mean(actionability_scores) if actionability_scores else 0.0

            duplicate_rate = duplicates / total_documents if total_documents > 0 else 0.0

            total_storage = sum(doc_sizes) / (1024 * 1024) if doc_sizes else 0.0  # MB
            avg_size = statistics.mean(doc_sizes) / 1024 if doc_sizes else 0.0  # KB

            # Get top 10 topics
            top_topics = dict(topics.most_common(10))

            snapshot = DriftSnapshot(
                timestamp=datetime.now().isoformat(),
                total_documents=len(unique_doc_ids),
                total_chunks=total_documents,
                doc_types=dict(doc_types),
                sources=dict(sources),
                topics=top_topics,
                avg_signalness=avg_signalness,
                avg_quality_score=avg_quality,
                avg_novelty_score=avg_novelty,
                avg_actionability_score=avg_actionability,
                duplicate_count=duplicates,
                duplicate_rate=duplicate_rate,
                docs_last_24h=docs_24h,
                docs_last_7d=docs_7d,
                docs_last_30d=docs_30d,
                total_storage_mb=total_storage,
                avg_doc_size_kb=avg_size
            )

            self.snapshots.append(snapshot)
            self._save_snapshot(snapshot)

            logger.info(f"Captured drift snapshot: {total_documents} docs, signalness={avg_signalness:.3f}")

            return snapshot

        except Exception as e:
            logger.error(f"Failed to capture snapshot: {e}")
            raise

    def _save_snapshot(self, snapshot: DriftSnapshot) -> bool:
        """Save snapshot to JSON file"""
        try:
            timestamp = datetime.fromisoformat(snapshot.timestamp)
            filename = f"snapshot_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
            file_path = self.snapshots_dir / filename

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(snapshot), f, indent=2)

            return True
        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")
            return False

    def load_snapshots(self, limit: int = 30) -> List[DriftSnapshot]:
        """
        Load recent snapshots from disk

        Args:
            limit: Maximum number of snapshots to load

        Returns:
            List of DriftSnapshot objects (newest first)
        """
        try:
            snapshot_files = sorted(
                self.snapshots_dir.glob("snapshot_*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )

            snapshots = []
            for file_path in snapshot_files[:limit]:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                snapshot = DriftSnapshot(**data)
                snapshots.append(snapshot)

            self.snapshots = snapshots
            logger.info(f"Loaded {len(snapshots)} drift snapshots")

            return snapshots

        except Exception as e:
            logger.error(f"Failed to load snapshots: {e}")
            return []

    def detect_drift(
        self,
        current: DriftSnapshot,
        baseline: DriftSnapshot
    ) -> List[DriftAlert]:
        """
        Detect drift between current and baseline snapshots

        Args:
            current: Current snapshot
            baseline: Baseline snapshot for comparison

        Returns:
            List of DriftAlert objects
        """
        alerts = []
        alert_counter = 0

        # Signalness drift
        if baseline.avg_signalness > 0:
            signalness_change = (current.avg_signalness - baseline.avg_signalness) / baseline.avg_signalness
            if abs(signalness_change) > self.thresholds['signalness_drop']:
                severity = "critical" if signalness_change < -0.25 else "warning"
                alert_counter += 1
                alerts.append(DriftAlert(
                    alert_id=f"drift_{alert_counter:03d}",
                    timestamp=current.timestamp,
                    severity=severity,
                    category="quality",
                    metric="avg_signalness",
                    message=f"Signalness {'decreased' if signalness_change < 0 else 'increased'} by {abs(signalness_change)*100:.1f}%",
                    current_value=current.avg_signalness,
                    baseline_value=baseline.avg_signalness,
                    threshold=self.thresholds['signalness_drop'],
                    deviation_pct=signalness_change * 100
                ))

        # Quality score drift
        if baseline.avg_quality_score > 0:
            quality_change = (current.avg_quality_score - baseline.avg_quality_score) / baseline.avg_quality_score
            if abs(quality_change) > self.thresholds['quality_drop']:
                severity = "warning"
                alert_counter += 1
                alerts.append(DriftAlert(
                    alert_id=f"drift_{alert_counter:03d}",
                    timestamp=current.timestamp,
                    severity=severity,
                    category="quality",
                    metric="avg_quality_score",
                    message=f"Quality score {'decreased' if quality_change < 0 else 'increased'} by {abs(quality_change)*100:.1f}%",
                    current_value=current.avg_quality_score,
                    baseline_value=baseline.avg_quality_score,
                    threshold=self.thresholds['quality_drop'],
                    deviation_pct=quality_change * 100
                ))

        # Duplicate rate drift
        if baseline.duplicate_rate < current.duplicate_rate:
            rate_change = current.duplicate_rate - baseline.duplicate_rate
            if rate_change > self.thresholds['duplicate_rate_increase']:
                severity = "warning"
                alert_counter += 1
                alerts.append(DriftAlert(
                    alert_id=f"drift_{alert_counter:03d}",
                    timestamp=current.timestamp,
                    severity=severity,
                    category="duplicates",
                    metric="duplicate_rate",
                    message=f"Duplicate rate increased by {rate_change*100:.1f} percentage points",
                    current_value=current.duplicate_rate,
                    baseline_value=baseline.duplicate_rate,
                    threshold=self.thresholds['duplicate_rate_increase'],
                    deviation_pct=rate_change * 100
                ))

        # Ingestion spike detection
        if baseline.docs_last_24h > 0:
            ingestion_ratio = current.docs_last_24h / baseline.docs_last_24h
            if ingestion_ratio > self.thresholds['ingestion_spike']:
                severity = "info"
                alert_counter += 1
                alerts.append(DriftAlert(
                    alert_id=f"drift_{alert_counter:03d}",
                    timestamp=current.timestamp,
                    severity=severity,
                    category="ingestion",
                    metric="docs_last_24h",
                    message=f"Ingestion spike: {ingestion_ratio:.1f}x baseline rate",
                    current_value=float(current.docs_last_24h),
                    baseline_value=float(baseline.docs_last_24h),
                    threshold=self.thresholds['ingestion_spike'],
                    deviation_pct=(ingestion_ratio - 1) * 100
                ))

        # Topic distribution drift
        baseline_topics = set(baseline.topics.keys())
        current_topics = set(current.topics.keys())

        new_topics = current_topics - baseline_topics
        if len(new_topics) > 0.25 * len(baseline_topics):  # >25% new topics
            severity = "info"
            alert_counter += 1
            alerts.append(DriftAlert(
                alert_id=f"drift_{alert_counter:03d}",
                timestamp=current.timestamp,
                severity=severity,
                category="domain",
                metric="topics",
                message=f"Topic distribution shift: {len(new_topics)} new topics appeared",
                current_value=float(len(current_topics)),
                baseline_value=float(len(baseline_topics)),
                threshold=self.thresholds['topic_shift'],
                deviation_pct=len(new_topics) / len(baseline_topics) * 100 if baseline_topics else 0
            ))

        self.alerts.extend(alerts)
        return alerts

    def generate_drift_report(
        self,
        current: DriftSnapshot,
        baseline: DriftSnapshot,
        baseline_period_desc: str = "baseline",
        current_period_desc: str = "current"
    ) -> DriftReport:
        """
        Generate comprehensive drift analysis report

        Args:
            current: Current snapshot
            baseline: Baseline snapshot
            baseline_period_desc: Description of baseline period
            current_period_desc: Description of current period

        Returns:
            DriftReport object
        """
        # Detect drift
        alerts = self.detect_drift(current, baseline)

        # Analyze trends
        trends = {}

        if baseline.avg_signalness > 0:
            if current.avg_signalness > baseline.avg_signalness * 1.05:
                trends['signalness'] = "increasing"
            elif current.avg_signalness < baseline.avg_signalness * 0.95:
                trends['signalness'] = "decreasing"
            else:
                trends['signalness'] = "stable"

        if baseline.duplicate_rate > 0:
            if current.duplicate_rate > baseline.duplicate_rate * 1.1:
                trends['duplicates'] = "increasing"
            elif current.duplicate_rate < baseline.duplicate_rate * 0.9:
                trends['duplicates'] = "decreasing"
            else:
                trends['duplicates'] = "stable"

        # Generate recommendations
        recommendations = []

        critical_alerts = [a for a in alerts if a.severity == "critical"]
        if critical_alerts:
            recommendations.append("CRITICAL: Investigate quality score drops immediately")

        if current.duplicate_rate > 0.15:
            recommendations.append("High duplicate rate detected - review deduplication settings")

        if current.avg_signalness < 0.5:
            recommendations.append("Low signalness - consider adjusting quality gates or improving enrichment")

        if len(current.topics) < len(baseline.topics) * 0.7:
            recommendations.append("Topic diversity decreasing - check if ingestion sources have narrowed")

        report = DriftReport(
            report_id=f"drift_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            timestamp=datetime.now().isoformat(),
            baseline_period=baseline_period_desc,
            current_period=current_period_desc,
            current_snapshot=current,
            baseline_snapshot=baseline,
            alerts=alerts,
            trends=trends,
            recommendations=recommendations
        )

        return report

    def get_dashboard_data(self, days: int = 30) -> Dict:
        """
        Get data for drift monitoring dashboard

        Args:
            days: Number of days of history to include

        Returns:
            Dict with time-series data for dashboard visualization
        """
        if not self.snapshots:
            self.load_snapshots(limit=days * 4)  # ~4 snapshots per day

        cutoff = datetime.now() - timedelta(days=days)
        recent_snapshots = [
            s for s in self.snapshots
            if datetime.fromisoformat(s.timestamp) > cutoff
        ]

        # Time series data
        timestamps = [s.timestamp for s in recent_snapshots]
        signalness_series = [s.avg_signalness for s in recent_snapshots]
        quality_series = [s.avg_quality_score for s in recent_snapshots]
        duplicate_rate_series = [s.duplicate_rate * 100 for s in recent_snapshots]
        doc_count_series = [s.total_documents for s in recent_snapshots]

        # Current vs baseline
        current = recent_snapshots[0] if recent_snapshots else None
        baseline = recent_snapshots[-1] if len(recent_snapshots) > 1 else current

        dashboard_data = {
            'time_series': {
                'timestamps': timestamps,
                'signalness': signalness_series,
                'quality': quality_series,
                'duplicate_rate': duplicate_rate_series,
                'document_count': doc_count_series
            },
            'current_metrics': {
                'total_documents': current.total_documents if current else 0,
                'avg_signalness': current.avg_signalness if current else 0.0,
                'duplicate_rate': current.duplicate_rate if current else 0.0,
                'docs_last_24h': current.docs_last_24h if current else 0
            } if current else {},
            'alerts': [asdict(a) for a in self.alerts[-10:]],  # Last 10 alerts
            'top_topics': current.topics if current else {},
            'doc_type_distribution': current.doc_types if current else {},
            'source_distribution': current.sources if current else {}
        }

        return dashboard_data
