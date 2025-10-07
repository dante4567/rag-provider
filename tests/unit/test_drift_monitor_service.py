"""
Unit tests for DriftMonitorService

Tests drift detection including:
- Snapshot capture
- Drift detection (signalness, quality, duplicates, ingestion)
- Alert generation
- Trend analysis
- Dashboard data generation
"""
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from src.services.drift_monitor_service import (
    DriftMonitorService,
    DriftSnapshot,
    DriftAlert,
    DriftReport
)


# =============================================================================
# DriftMonitorService Tests
# =============================================================================

class TestDriftMonitorService:
    """Test the DriftMonitorService class"""

    @pytest.fixture
    def service(self, tmp_path):
        """Create DriftMonitorService with temp directory"""
        snapshots_dir = tmp_path / "snapshots"
        return DriftMonitorService(snapshots_dir=str(snapshots_dir))

    @pytest.fixture
    def mock_collection(self):
        """Create mock ChromaDB collection"""
        class MockCollection:
            def get(self):
                return {
                    'ids': ['chunk1', 'chunk2', 'chunk3'],
                    'metadatas': [
                        {
                            'document_id': 'doc1',
                            'file_type': 'pdf',
                            'source': 'upload',
                            'topics': ['ai', 'ml'],
                            'signalness': 0.75,
                            'quality_score': 0.80,
                            'novelty_score': 0.60,
                            'actionability_score': 0.70,
                            'content_hash': 'hash1',
                            'ingested_at': datetime.now().isoformat(),
                            'file_size_bytes': 1024000
                        },
                        {
                            'document_id': 'doc2',
                            'file_type': 'word',
                            'source': 'email',
                            'topics': ['ai'],
                            'signalness': 0.65,
                            'quality_score': 0.70,
                            'novelty_score': 0.50,
                            'actionability_score': 0.60,
                            'content_hash': 'hash2',
                            'ingested_at': datetime.now().isoformat(),
                            'file_size_bytes': 512000
                        },
                        {
                            'document_id': 'doc3',
                            'file_type': 'pdf',
                            'source': 'upload',
                            'topics': ['ml', 'data'],
                            'signalness': 0.85,
                            'quality_score': 0.90,
                            'novelty_score': 0.70,
                            'actionability_score': 0.80,
                            'content_hash': 'hash3',
                            'ingested_at': datetime.now().isoformat(),
                            'file_size_bytes': 2048000
                        }
                    ]
                }
        return MockCollection()

    def test_init(self, service):
        """Test DriftMonitorService initialization"""
        assert service is not None
        assert service.snapshots == []
        assert service.alerts == []
        assert service.snapshots_dir.exists()

    def test_capture_snapshot_basic(self, service, mock_collection):
        """Test capturing basic snapshot"""
        snapshot = service.capture_snapshot(mock_collection)

        assert snapshot is not None
        assert snapshot.total_documents == 3
        assert snapshot.total_chunks == 3
        assert isinstance(snapshot.timestamp, str)

    def test_capture_snapshot_doc_types(self, service, mock_collection):
        """Test snapshot captures document types"""
        snapshot = service.capture_snapshot(mock_collection)

        assert 'pdf' in snapshot.doc_types
        assert 'word' in snapshot.doc_types
        assert snapshot.doc_types['pdf'] == 2
        assert snapshot.doc_types['word'] == 1

    def test_capture_snapshot_sources(self, service, mock_collection):
        """Test snapshot captures sources"""
        snapshot = service.capture_snapshot(mock_collection)

        assert 'upload' in snapshot.sources
        assert 'email' in snapshot.sources

    def test_capture_snapshot_topics(self, service, mock_collection):
        """Test snapshot captures topics"""
        snapshot = service.capture_snapshot(mock_collection)

        assert 'ai' in snapshot.topics
        assert 'ml' in snapshot.topics
        assert snapshot.topics['ai'] == 2  # Appears in 2 docs

    def test_capture_snapshot_calculates_averages(self, service, mock_collection):
        """Test snapshot calculates score averages"""
        snapshot = service.capture_snapshot(mock_collection)

        # Average signalness: (0.75 + 0.65 + 0.85) / 3 = 0.75
        assert snapshot.avg_signalness == pytest.approx(0.75, rel=0.01)
        # Average quality: (0.80 + 0.70 + 0.90) / 3 = 0.80
        assert snapshot.avg_quality_score == pytest.approx(0.80, rel=0.01)

    def test_capture_snapshot_empty_collection(self, service):
        """Test snapshot with empty collection"""
        class EmptyCollection:
            def get(self):
                return {'ids': [], 'metadatas': []}

        snapshot = service.capture_snapshot(EmptyCollection())

        assert snapshot.total_documents == 0
        assert snapshot.avg_signalness == 0.0
        assert snapshot.duplicate_rate == 0.0


# =============================================================================
# Drift Detection Tests
# =============================================================================

class TestDriftDetection:
    """Test drift detection logic"""

    @pytest.fixture
    def service(self):
        return DriftMonitorService()

    @pytest.fixture
    def baseline_snapshot(self):
        """Create baseline snapshot"""
        return DriftSnapshot(
            timestamp=(datetime.now() - timedelta(days=7)).isoformat(),
            total_documents=100,
            total_chunks=500,
            doc_types={'pdf': 60, 'word': 40},
            sources={'upload': 80, 'email': 20},
            topics={'ai': 30, 'ml': 25, 'data': 20},
            avg_signalness=0.75,
            avg_quality_score=0.80,
            avg_novelty_score=0.60,
            avg_actionability_score=0.70,
            duplicate_count=5,
            duplicate_rate=0.05,
            docs_last_24h=10,
            docs_last_7d=70,
            docs_last_30d=100,
            total_storage_mb=500.0,
            avg_doc_size_kb=500.0
        )

    def test_detect_signalness_drop(self, service, baseline_snapshot):
        """Test detection of signalness drop"""
        current = DriftSnapshot(
            timestamp=datetime.now().isoformat(),
            total_documents=110,
            total_chunks=550,
            doc_types={'pdf': 65, 'word': 45},
            sources={'upload': 90, 'email': 20},
            topics={'ai': 35, 'ml': 30, 'data': 25},
            avg_signalness=0.60,  # Dropped from 0.75 to 0.60 (20% drop)
            avg_quality_score=0.80,
            avg_novelty_score=0.60,
            avg_actionability_score=0.70,
            duplicate_count=5,
            duplicate_rate=0.045,
            docs_last_24h=12,
            docs_last_7d=80,
            docs_last_30d=110,
            total_storage_mb=550.0,
            avg_doc_size_kb=500.0
        )

        alerts = service.detect_drift(current, baseline_snapshot)

        signalness_alerts = [a for a in alerts if a.metric == 'avg_signalness']
        assert len(signalness_alerts) > 0
        assert signalness_alerts[0].category == 'quality'
        assert signalness_alerts[0].severity in ['warning', 'critical']

    def test_detect_duplicate_rate_increase(self, service, baseline_snapshot):
        """Test detection of duplicate rate increase"""
        current = DriftSnapshot(
            timestamp=datetime.now().isoformat(),
            total_documents=110,
            total_chunks=550,
            doc_types={'pdf': 65, 'word': 45},
            sources={'upload': 90, 'email': 20},
            topics={'ai': 35, 'ml': 30},
            avg_signalness=0.75,
            avg_quality_score=0.80,
            avg_novelty_score=0.60,
            avg_actionability_score=0.70,
            duplicate_count=20,
            duplicate_rate=0.18,  # Increased from 0.05 to 0.18
            docs_last_24h=12,
            docs_last_7d=80,
            docs_last_30d=110,
            total_storage_mb=550.0,
            avg_doc_size_kb=500.0
        )

        alerts = service.detect_drift(current, baseline_snapshot)

        dup_alerts = [a for a in alerts if a.metric == 'duplicate_rate']
        assert len(dup_alerts) > 0
        assert dup_alerts[0].category == 'duplicates'

    def test_detect_ingestion_spike(self, service, baseline_snapshot):
        """Test detection of ingestion spike"""
        current = DriftSnapshot(
            timestamp=datetime.now().isoformat(),
            total_documents=150,
            total_chunks=750,
            doc_types={'pdf': 90, 'word': 60},
            sources={'upload': 120, 'email': 30},
            topics={'ai': 50, 'ml': 40},
            avg_signalness=0.75,
            avg_quality_score=0.80,
            avg_novelty_score=0.60,
            avg_actionability_score=0.70,
            duplicate_count=7,
            duplicate_rate=0.047,
            docs_last_24h=40,  # 4x increase from 10
            docs_last_7d=120,
            docs_last_30d=150,
            total_storage_mb=750.0,
            avg_doc_size_kb=500.0
        )

        alerts = service.detect_drift(current, baseline_snapshot)

        ingestion_alerts = [a for a in alerts if a.metric == 'docs_last_24h']
        assert len(ingestion_alerts) > 0
        assert ingestion_alerts[0].category == 'ingestion'

    def test_no_drift_detected_stable(self, service, baseline_snapshot):
        """Test no drift when metrics are stable"""
        current = DriftSnapshot(
            timestamp=datetime.now().isoformat(),
            total_documents=105,
            total_chunks=525,
            doc_types={'pdf': 63, 'word': 42},
            sources={'upload': 84, 'email': 21},
            topics={'ai': 32, 'ml': 26, 'data': 21},
            avg_signalness=0.76,  # Slightly up but within threshold
            avg_quality_score=0.81,
            avg_novelty_score=0.61,
            avg_actionability_score=0.71,
            duplicate_count=5,
            duplicate_rate=0.048,  # Slightly down
            docs_last_24h=11,  # Slightly up
            docs_last_7d=74,
            docs_last_30d=105,
            total_storage_mb=525.0,
            avg_doc_size_kb=500.0
        )

        alerts = service.detect_drift(current, baseline_snapshot)

        # Should have no or minimal alerts for stable metrics
        critical_alerts = [a for a in alerts if a.severity == 'critical']
        assert len(critical_alerts) == 0


# =============================================================================
# Snapshot Persistence Tests
# =============================================================================

class TestSnapshotPersistence:
    """Test snapshot loading and saving"""

    @pytest.fixture
    def service(self, tmp_path):
        snapshots_dir = tmp_path / "snapshots"
        return DriftMonitorService(snapshots_dir=str(snapshots_dir))

    def test_save_snapshot(self, service):
        """Test saving snapshot to file"""
        snapshot = DriftSnapshot(
            timestamp=datetime.now().isoformat(),
            total_documents=100,
            total_chunks=500,
            doc_types={'pdf': 60},
            sources={'upload': 80},
            topics={'ai': 30},
            avg_signalness=0.75,
            avg_quality_score=0.80,
            avg_novelty_score=0.60,
            avg_actionability_score=0.70,
            duplicate_count=5,
            duplicate_rate=0.05,
            docs_last_24h=10,
            docs_last_7d=70,
            docs_last_30d=100,
            total_storage_mb=500.0,
            avg_doc_size_kb=500.0
        )

        success = service._save_snapshot(snapshot)
        assert success is True

        # Check file exists
        snapshot_files = list(service.snapshots_dir.glob("snapshot_*.json"))
        assert len(snapshot_files) > 0

    def test_load_snapshots(self, service):
        """Test loading snapshots from disk"""
        # Create and save snapshot
        snapshot = DriftSnapshot(
            timestamp=datetime.now().isoformat(),
            total_documents=100,
            total_chunks=500,
            doc_types={'pdf': 60},
            sources={'upload': 80},
            topics={'ai': 30},
            avg_signalness=0.75,
            avg_quality_score=0.80,
            avg_novelty_score=0.60,
            avg_actionability_score=0.70,
            duplicate_count=5,
            duplicate_rate=0.05,
            docs_last_24h=10,
            docs_last_7d=70,
            docs_last_30d=100,
            total_storage_mb=500.0,
            avg_doc_size_kb=500.0
        )
        service._save_snapshot(snapshot)

        # Load snapshots
        loaded = service.load_snapshots(limit=10)

        assert len(loaded) == 1
        assert loaded[0].total_documents == 100
        assert loaded[0].avg_signalness == 0.75


# =============================================================================
# Report Generation Tests
# =============================================================================

class TestReportGeneration:
    """Test drift report generation"""

    @pytest.fixture
    def service(self):
        return DriftMonitorService()

    @pytest.fixture
    def baseline_snapshot(self):
        return DriftSnapshot(
            timestamp=(datetime.now() - timedelta(days=7)).isoformat(),
            total_documents=100,
            total_chunks=500,
            doc_types={'pdf': 60, 'word': 40},
            sources={'upload': 80},
            topics={'ai': 30, 'ml': 25},
            avg_signalness=0.75,
            avg_quality_score=0.80,
            avg_novelty_score=0.60,
            avg_actionability_score=0.70,
            duplicate_count=5,
            duplicate_rate=0.05,
            docs_last_24h=10,
            docs_last_7d=70,
            docs_last_30d=100,
            total_storage_mb=500.0,
            avg_doc_size_kb=500.0
        )

    @pytest.fixture
    def current_snapshot(self):
        return DriftSnapshot(
            timestamp=datetime.now().isoformat(),
            total_documents=110,
            total_chunks=550,
            doc_types={'pdf': 65, 'word': 45},
            sources={'upload': 90},
            topics={'ai': 35, 'ml': 30},
            avg_signalness=0.78,
            avg_quality_score=0.82,
            avg_novelty_score=0.62,
            avg_actionability_score=0.72,
            duplicate_count=5,
            duplicate_rate=0.045,
            docs_last_24h=12,
            docs_last_7d=80,
            docs_last_30d=110,
            total_storage_mb=550.0,
            avg_doc_size_kb=500.0
        )

    def test_generate_drift_report(self, service, current_snapshot, baseline_snapshot):
        """Test drift report generation"""
        report = service.generate_drift_report(
            current_snapshot,
            baseline_snapshot,
            baseline_period_desc="Last week",
            current_period_desc="This week"
        )

        assert report is not None
        assert isinstance(report, DriftReport)
        assert report.baseline_period == "Last week"
        assert report.current_period == "This week"

    def test_report_includes_trends(self, service, current_snapshot, baseline_snapshot):
        """Test report includes trend analysis"""
        report = service.generate_drift_report(current_snapshot, baseline_snapshot)

        assert 'signalness' in report.trends
        assert report.trends['signalness'] in ['increasing', 'decreasing', 'stable']

    def test_report_includes_recommendations(self, service, baseline_snapshot):
        """Test report includes recommendations for issues"""
        # Create problematic snapshot
        current = DriftSnapshot(
            timestamp=datetime.now().isoformat(),
            total_documents=110,
            total_chunks=550,
            doc_types={'pdf': 65},
            sources={'upload': 90},
            topics={'ai': 35},
            avg_signalness=0.30,  # Very low signalness
            avg_quality_score=0.40,
            avg_novelty_score=0.30,
            avg_actionability_score=0.40,
            duplicate_count=20,
            duplicate_rate=0.20,  # High duplicate rate
            docs_last_24h=12,
            docs_last_7d=80,
            docs_last_30d=110,
            total_storage_mb=550.0,
            avg_doc_size_kb=500.0
        )

        report = service.generate_drift_report(current, baseline_snapshot)

        assert len(report.recommendations) > 0
        # Should recommend investigating quality issues
        quality_recs = [r for r in report.recommendations if 'quality' in r.lower() or 'signalness' in r.lower()]
        assert len(quality_recs) > 0


# =============================================================================
# Dashboard Data Tests
# =============================================================================

class TestDashboardData:
    """Test dashboard data generation"""

    @pytest.fixture
    def service(self, tmp_path):
        service = DriftMonitorService(snapshots_dir=str(tmp_path / "snapshots"))

        # Add sample snapshots
        for i in range(5):
            snapshot = DriftSnapshot(
                timestamp=(datetime.now() - timedelta(days=i)).isoformat(),
                total_documents=100 + i * 10,
                total_chunks=500 + i * 50,
                doc_types={'pdf': 60},
                sources={'upload': 80},
                topics={'ai': 30},
                avg_signalness=0.75 - i * 0.01,
                avg_quality_score=0.80,
                avg_novelty_score=0.60,
                avg_actionability_score=0.70,
                duplicate_count=5,
                duplicate_rate=0.05,
                docs_last_24h=10,
                docs_last_7d=70,
                docs_last_30d=100,
                total_storage_mb=500.0,
                avg_doc_size_kb=500.0
            )
            service.snapshots.append(snapshot)

        return service

    def test_get_dashboard_data(self, service):
        """Test dashboard data generation"""
        dashboard_data = service.get_dashboard_data(days=30)

        assert 'time_series' in dashboard_data
        assert 'current_metrics' in dashboard_data
        assert 'alerts' in dashboard_data

    def test_dashboard_time_series(self, service):
        """Test dashboard includes time series data"""
        dashboard_data = service.get_dashboard_data(days=30)

        time_series = dashboard_data['time_series']
        assert 'timestamps' in time_series
        assert 'signalness' in time_series
        assert 'quality' in time_series
        assert len(time_series['timestamps']) == 5

    def test_dashboard_current_metrics(self, service):
        """Test dashboard includes current metrics"""
        dashboard_data = service.get_dashboard_data(days=30)

        current = dashboard_data['current_metrics']
        assert 'total_documents' in current
        assert 'avg_signalness' in current
        assert 'duplicate_rate' in current


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.fixture
    def service(self):
        return DriftMonitorService()

    def test_detect_drift_with_zero_baseline(self, service):
        """Test drift detection handles zero baseline values"""
        baseline = DriftSnapshot(
            timestamp=datetime.now().isoformat(),
            total_documents=0,
            total_chunks=0,
            doc_types={},
            sources={},
            topics={},
            avg_signalness=0.0,  # Zero baseline
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

        current = DriftSnapshot(
            timestamp=datetime.now().isoformat(),
            total_documents=10,
            total_chunks=50,
            doc_types={'pdf': 10},
            sources={'upload': 10},
            topics={'ai': 5},
            avg_signalness=0.75,
            avg_quality_score=0.80,
            avg_novelty_score=0.60,
            avg_actionability_score=0.70,
            duplicate_count=1,
            duplicate_rate=0.10,
            docs_last_24h=10,
            docs_last_7d=10,
            docs_last_30d=10,
            total_storage_mb=50.0,
            avg_doc_size_kb=500.0
        )

        # Should not crash
        alerts = service.detect_drift(current, baseline)
        assert isinstance(alerts, list)
