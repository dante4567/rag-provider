"""
Unit tests for Monitoring Service

Tests structured logging, metrics collection, health checks, and observability
"""

import pytest
import json
import time
from datetime import datetime
from src.services.monitoring_service import (
    StructuredLogger,
    MetricsCollector,
    HealthCheckMonitor,
    MonitoringService,
    HealthStatus,
    MetricPoint,
    HealthCheck
)


# =============================================================================
# Data Classes Tests
# =============================================================================

class TestDataClasses:
    """Test data classes"""

    def test_metric_point_creation(self):
        """Test MetricPoint creation"""
        point = MetricPoint(name="test_metric", value=42.0)
        assert point.name == "test_metric"
        assert point.value == 42.0
        assert isinstance(point.timestamp, datetime)
        assert point.labels == {}

    def test_metric_point_with_labels(self):
        """Test MetricPoint with labels"""
        point = MetricPoint(
            name="requests",
            value=100,
            labels={"endpoint": "/search", "method": "POST"}
        )
        assert point.labels["endpoint"] == "/search"
        assert point.labels["method"] == "POST"

    def test_health_check_creation(self):
        """Test HealthCheck creation"""
        check = HealthCheck(
            component="database",
            status=HealthStatus.HEALTHY,
            message="DB OK"
        )
        assert check.component == "database"
        assert check.status == HealthStatus.HEALTHY
        assert check.message == "DB OK"
        assert isinstance(check.timestamp, datetime)

    def test_health_status_enum(self):
        """Test HealthStatus enum values"""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"


# =============================================================================
# Structured Logger Tests
# =============================================================================

class TestStructuredLogger:
    """Test structured JSON logging"""

    def test_logger_initialization(self):
        """Test logger initialization"""
        logger = StructuredLogger("test_service")
        assert logger.service_name == "test_service"
        assert logger.logger is not None

    def test_log_creates_json(self, caplog):
        """Test log creates valid JSON"""
        logger = StructuredLogger("test_service")

        with caplog.at_level("INFO", logger="test_service"):
            logger.log("info", "Test message", user_id=123)

        # Parse logged JSON
        assert len(caplog.records) > 0
        log_entry = json.loads(caplog.records[-1].message)

        assert log_entry["level"] == "INFO"
        assert log_entry["service"] == "test_service"
        assert log_entry["message"] == "Test message"
        assert log_entry["user_id"] == 123
        assert "timestamp" in log_entry

    def test_info_logging(self, caplog):
        """Test info level logging"""
        logger = StructuredLogger("test_service")

        with caplog.at_level("INFO", logger="test_service"):
            logger.info("Info message", action="test")

        log_entry = json.loads(caplog.records[-1].message)
        assert log_entry["level"] == "INFO"
        assert log_entry["message"] == "Info message"

    def test_warning_logging(self, caplog):
        """Test warning level logging"""
        logger = StructuredLogger("test_service")

        with caplog.at_level("WARNING", logger="test_service"):
            logger.warning("Warning message", severity="medium")

        log_entry = json.loads(caplog.records[-1].message)
        assert log_entry["level"] == "WARNING"
        assert log_entry["message"] == "Warning message"

    def test_error_logging(self, caplog):
        """Test error level logging"""
        logger = StructuredLogger("test_service")

        with caplog.at_level("ERROR", logger="test_service"):
            logger.error("Error message", error_code=500)

        log_entry = json.loads(caplog.records[-1].message)
        assert log_entry["level"] == "ERROR"
        assert log_entry["message"] == "Error message"

    def test_metric_logging(self, caplog):
        """Test metric logging"""
        logger = StructuredLogger("test_service")

        with caplog.at_level("INFO", logger="test_service"):
            logger.metric("request_count", 42, endpoint="/search")

        log_entry = json.loads(caplog.records[-1].message)
        assert log_entry["metric"] == "request_count"
        assert log_entry["value"] == 42
        assert log_entry["labels"]["endpoint"] == "/search"


# =============================================================================
# Metrics Collector Tests
# =============================================================================

class TestMetricsCollector:
    """Test metrics collection and aggregation"""

    def test_counter_increment(self):
        """Test counter increment"""
        collector = MetricsCollector()
        collector.increment_counter("requests")
        collector.increment_counter("requests")
        collector.increment_counter("requests", value=3)

        assert collector.get_counter("requests") == 5.0

    def test_counter_with_labels(self):
        """Test counter with labels"""
        collector = MetricsCollector()
        collector.increment_counter("requests", labels={"endpoint": "/search"})
        collector.increment_counter("requests", labels={"endpoint": "/ingest"})
        collector.increment_counter("requests", labels={"endpoint": "/search"})

        assert collector.get_counter("requests", {"endpoint": "/search"}) == 2.0
        assert collector.get_counter("requests", {"endpoint": "/ingest"}) == 1.0

    def test_counter_default_value(self):
        """Test counter default value is 0"""
        collector = MetricsCollector()
        assert collector.get_counter("nonexistent") == 0.0

    def test_gauge_set(self):
        """Test gauge setting"""
        collector = MetricsCollector()
        collector.set_gauge("memory_mb", 512.0)
        collector.set_gauge("memory_mb", 768.0)  # Overwrite

        assert collector.get_gauge("memory_mb") == 768.0

    def test_gauge_with_labels(self):
        """Test gauge with labels"""
        collector = MetricsCollector()
        collector.set_gauge("cpu_percent", 45.5, labels={"core": "0"})
        collector.set_gauge("cpu_percent", 67.8, labels={"core": "1"})

        assert collector.get_gauge("cpu_percent", {"core": "0"}) == 45.5
        assert collector.get_gauge("cpu_percent", {"core": "1"}) == 67.8

    def test_gauge_default_value(self):
        """Test gauge default value is 0"""
        collector = MetricsCollector()
        assert collector.get_gauge("nonexistent") == 0.0

    def test_histogram_observe(self):
        """Test histogram observations"""
        collector = MetricsCollector()
        collector.observe_histogram("latency_ms", 10.0)
        collector.observe_histogram("latency_ms", 20.0)
        collector.observe_histogram("latency_ms", 30.0)

        stats = collector.get_histogram_stats("latency_ms")
        assert stats["count"] == 3
        assert stats["sum"] == 60.0
        assert stats["avg"] == 20.0
        assert stats["min"] == 10.0
        assert stats["max"] == 30.0

    def test_histogram_percentiles(self):
        """Test histogram percentile calculations"""
        collector = MetricsCollector()

        # Add 100 values
        for i in range(100):
            collector.observe_histogram("response_time", float(i))

        stats = collector.get_histogram_stats("response_time")
        assert stats["count"] == 100
        assert stats["p50"] == 50.0
        assert stats["p95"] == 95.0
        assert stats["p99"] == 99.0

    def test_histogram_single_value(self):
        """Test histogram with single value"""
        collector = MetricsCollector()
        collector.observe_histogram("test", 42.0)

        stats = collector.get_histogram_stats("test")
        assert stats["count"] == 1
        assert stats["avg"] == 42.0
        assert stats["p50"] == 42.0
        assert stats["p95"] == 42.0

    def test_histogram_empty(self):
        """Test empty histogram"""
        collector = MetricsCollector()
        stats = collector.get_histogram_stats("nonexistent")

        assert stats["count"] == 0
        assert stats["sum"] == 0
        assert stats["avg"] == 0

    def test_get_all_metrics(self):
        """Test getting all metrics"""
        collector = MetricsCollector()
        collector.increment_counter("requests", value=10)
        collector.set_gauge("memory", 512.0)
        collector.observe_histogram("latency", 100.0)

        all_metrics = collector.get_all_metrics()

        assert "counters" in all_metrics
        assert "gauges" in all_metrics
        assert "histograms" in all_metrics
        assert all_metrics["counters"]["requests"] == 10.0
        assert all_metrics["gauges"]["memory"] == 512.0

    def test_metric_history_recording(self):
        """Test metrics are recorded in history"""
        collector = MetricsCollector()
        collector.increment_counter("test", value=1.0)
        collector.set_gauge("test_gauge", 2.0)

        assert len(collector.metric_history) >= 2

    def test_metric_history_limit(self):
        """Test metric history is limited to 1000 entries"""
        collector = MetricsCollector()

        # Add 1500 metrics
        for i in range(1500):
            collector.increment_counter(f"metric_{i}")

        # Should be capped at 1000
        assert len(collector.metric_history) == 1000

    def test_label_key_generation(self):
        """Test label key generation"""
        collector = MetricsCollector()

        # Same metric with different labels
        collector.increment_counter("req", labels={"a": "1", "b": "2"})
        collector.increment_counter("req", labels={"b": "2", "a": "1"})  # Different order

        # Should be same key (labels sorted)
        assert collector.get_counter("req", {"a": "1", "b": "2"}) == 2.0


# =============================================================================
# Health Check Monitor Tests
# =============================================================================

class TestHealthCheckMonitor:
    """Test health check monitoring"""

    def test_check_component_healthy(self):
        """Test checking healthy component"""
        monitor = HealthCheckMonitor()

        def check_func():
            return (HealthStatus.HEALTHY, "Component OK")

        result = monitor.check_component("test_component", check_func)

        assert result.component == "test_component"
        assert result.status == HealthStatus.HEALTHY
        assert result.message == "Component OK"
        assert result.response_time_ms is not None
        assert result.response_time_ms >= 0

    def test_check_component_degraded(self):
        """Test checking degraded component"""
        monitor = HealthCheckMonitor()

        def check_func():
            return (HealthStatus.DEGRADED, "Slow response")

        result = monitor.check_component("test_component", check_func)

        assert result.status == HealthStatus.DEGRADED
        assert result.message == "Slow response"

    def test_check_component_exception(self):
        """Test component check that raises exception"""
        monitor = HealthCheckMonitor()

        def check_func():
            raise ValueError("Connection failed")

        result = monitor.check_component("test_component", check_func)

        assert result.status == HealthStatus.UNHEALTHY
        assert "Check failed" in result.message
        assert "Connection failed" in result.message

    def test_check_component_timeout_detection(self):
        """Test slow check is marked as degraded"""
        monitor = HealthCheckMonitor()

        def slow_check():
            time.sleep(0.1)  # 100ms
            return (HealthStatus.HEALTHY, "OK")

        result = monitor.check_component("test", slow_check, timeout_seconds=0.05)

        assert result.status == HealthStatus.DEGRADED
        assert "slow:" in result.message

    def test_component_status_tracking(self):
        """Test component status is tracked"""
        monitor = HealthCheckMonitor()

        def healthy_check():
            return (HealthStatus.HEALTHY, "OK")

        monitor.check_component("db", healthy_check)

        assert "db" in monitor.component_status
        assert monitor.component_status["db"] == HealthStatus.HEALTHY

    def test_multiple_checks_tracked(self):
        """Test multiple checks are tracked"""
        monitor = HealthCheckMonitor()

        def check_func():
            return (HealthStatus.HEALTHY, "OK")

        monitor.check_component("db", check_func)
        monitor.check_component("cache", check_func)
        monitor.check_component("api", check_func)

        assert len(monitor.component_status) == 3
        assert len(monitor.health_checks) == 3

    def test_health_check_history_limit(self):
        """Test health check history is limited to 100"""
        monitor = HealthCheckMonitor()

        def check_func():
            return (HealthStatus.HEALTHY, "OK")

        # Add 150 checks
        for i in range(150):
            monitor.check_component(f"component_{i}", check_func)

        # Should be capped at 100
        assert len(monitor.health_checks) == 100

    def test_get_overall_health_all_healthy(self):
        """Test overall health with all components healthy"""
        monitor = HealthCheckMonitor()

        def healthy_check():
            return (HealthStatus.HEALTHY, "OK")

        monitor.check_component("db", healthy_check)
        monitor.check_component("cache", healthy_check)

        assert monitor.get_overall_health() == HealthStatus.HEALTHY

    def test_get_overall_health_degraded(self):
        """Test overall health with degraded component"""
        monitor = HealthCheckMonitor()

        monitor.check_component("db", lambda: (HealthStatus.HEALTHY, "OK"))
        monitor.check_component("cache", lambda: (HealthStatus.DEGRADED, "Slow"))

        assert monitor.get_overall_health() == HealthStatus.DEGRADED

    def test_get_overall_health_unhealthy(self):
        """Test overall health with unhealthy component"""
        monitor = HealthCheckMonitor()

        monitor.check_component("db", lambda: (HealthStatus.HEALTHY, "OK"))
        monitor.check_component("cache", lambda: (HealthStatus.DEGRADED, "Slow"))
        monitor.check_component("api", lambda: (HealthStatus.UNHEALTHY, "Down"))

        # Worst status wins
        assert monitor.get_overall_health() == HealthStatus.UNHEALTHY

    def test_get_overall_health_empty(self):
        """Test overall health with no checks"""
        monitor = HealthCheckMonitor()
        assert monitor.get_overall_health() == HealthStatus.HEALTHY

    def test_get_health_summary(self):
        """Test health summary"""
        monitor = HealthCheckMonitor()

        monitor.check_component("db", lambda: (HealthStatus.HEALTHY, "OK"))
        monitor.check_component("cache", lambda: (HealthStatus.DEGRADED, "Slow"))

        summary = monitor.get_health_summary()

        assert summary["overall"] == "degraded"
        assert "db" in summary["components"]
        assert "cache" in summary["components"]
        assert len(summary["last_checks"]) == 2


# =============================================================================
# Monitoring Service Tests
# =============================================================================

class TestMonitoringService:
    """Test complete monitoring service"""

    def test_service_initialization(self):
        """Test service initialization"""
        service = MonitoringService("test_service")

        assert service.service_name == "test_service"
        assert service.logger is not None
        assert service.metrics is not None
        assert service.health is not None
        assert isinstance(service.start_time, datetime)

    def test_log_request(self, caplog):
        """Test HTTP request logging"""
        service = MonitoringService("test")

        with caplog.at_level("INFO", logger="test"):
            service.log_request("/search", "POST", 200, 123.4)

        # Check log entry
        log_entry = json.loads(caplog.records[-1].message)
        assert log_entry["endpoint"] == "/search"
        assert log_entry["method"] == "POST"
        assert log_entry["status_code"] == 200

        # Check metrics
        counter_value = service.metrics.get_counter(
            "http_requests_total",
            {"endpoint": "/search", "method": "POST", "status": "200"}
        )
        assert counter_value == 1.0

    def test_log_request_multiple(self):
        """Test logging multiple requests"""
        service = MonitoringService("test")

        service.log_request("/search", "POST", 200, 100.0)
        service.log_request("/search", "POST", 200, 150.0)
        service.log_request("/ingest", "POST", 201, 200.0)

        # Check counter
        search_count = service.metrics.get_counter(
            "http_requests_total",
            {"endpoint": "/search", "method": "POST", "status": "200"}
        )
        assert search_count == 2.0

        # Check histogram
        stats = service.metrics.get_histogram_stats(
            "http_request_duration_ms",
            {"endpoint": "/search"}
        )
        assert stats["count"] == 2
        assert stats["avg"] == 125.0

    def test_log_error(self, caplog):
        """Test error logging"""
        service = MonitoringService("test")

        with caplog.at_level("ERROR", logger="test"):
            service.log_error("ValueError", "Invalid input", user_id=123)

        # Check log
        log_entry = json.loads(caplog.records[-1].message)
        assert log_entry["error_type"] == "ValueError"
        assert log_entry["message"] == "Invalid input"

        # Check metric
        error_count = service.metrics.get_counter(
            "errors_total",
            {"error_type": "ValueError"}
        )
        assert error_count == 1.0

    def test_track_operation(self):
        """Test operation tracking"""
        service = MonitoringService("test")
        service.track_operation("search", 123.4, success=True, source="api")

        # Check counter
        counter = service.metrics.get_counter(
            "search_total",
            {"source": "api", "success": "True"}
        )
        assert counter == 1.0

        # Check histogram
        stats = service.metrics.get_histogram_stats(
            "search_duration_ms",
            {"source": "api"}
        )
        assert stats["count"] == 1
        assert stats["avg"] == 123.4

    def test_track_operation_failure(self):
        """Test tracking failed operation"""
        service = MonitoringService("test")
        service.track_operation("ingest", 50.0, success=False)

        counter = service.metrics.get_counter(
            "ingest_total",
            {"success": "False"}
        )
        assert counter == 1.0

    def test_get_uptime_seconds(self):
        """Test uptime calculation"""
        service = MonitoringService("test")
        time.sleep(0.1)

        uptime = service.get_uptime_seconds()
        assert uptime >= 0.1

    def test_get_monitoring_summary(self):
        """Test monitoring summary"""
        service = MonitoringService("test_service")

        # Add some data
        service.log_request("/search", "GET", 200, 100.0)
        service.metrics.set_gauge("memory_mb", 512.0)
        service.health.check_component("db", lambda: (HealthStatus.HEALTHY, "OK"))

        summary = service.get_monitoring_summary()

        assert summary["service"] == "test_service"
        assert summary["uptime_seconds"] >= 0
        assert "health" in summary
        assert "metrics" in summary
        assert summary["health"]["overall"] == "healthy"

    def test_monitoring_summary_structure(self):
        """Test monitoring summary has correct structure"""
        service = MonitoringService("test")
        summary = service.get_monitoring_summary()

        # Check structure
        assert "service" in summary
        assert "uptime_seconds" in summary
        assert "health" in summary
        assert "metrics" in summary

        # Check health structure
        assert "overall" in summary["health"]
        assert "components" in summary["health"]
        assert "last_checks" in summary["health"]

        # Check metrics structure
        assert "counters" in summary["metrics"]
        assert "gauges" in summary["metrics"]
        assert "histograms" in summary["metrics"]


# =============================================================================
# Integration Tests
# =============================================================================

class TestMonitoringIntegration:
    """Test monitoring service integration scenarios"""

    def test_complete_request_lifecycle(self):
        """Test complete request monitoring lifecycle"""
        service = MonitoringService("api")

        # Simulate request
        start_time = time.time()
        time.sleep(0.01)  # Simulate processing
        duration_ms = (time.time() - start_time) * 1000

        service.log_request("/search", "POST", 200, duration_ms)

        # Verify logging and metrics
        counter = service.metrics.get_counter(
            "http_requests_total",
            {"endpoint": "/search", "method": "POST", "status": "200"}
        )
        assert counter == 1.0

    def test_error_tracking_scenario(self):
        """Test error tracking scenario"""
        service = MonitoringService("api")

        # Log multiple errors
        service.log_error("DatabaseError", "Connection timeout")
        service.log_error("DatabaseError", "Query failed")
        service.log_error("ValidationError", "Invalid input")

        # Check error counts
        db_errors = service.metrics.get_counter(
            "errors_total",
            {"error_type": "DatabaseError"}
        )
        val_errors = service.metrics.get_counter(
            "errors_total",
            {"error_type": "ValidationError"}
        )

        assert db_errors == 2.0
        assert val_errors == 1.0

    def test_health_monitoring_scenario(self):
        """Test health monitoring scenario"""
        service = MonitoringService("api")

        # Check multiple components
        service.health.check_component("db", lambda: (HealthStatus.HEALTHY, "OK"))
        service.health.check_component("cache", lambda: (HealthStatus.HEALTHY, "OK"))
        service.health.check_component("storage", lambda: (HealthStatus.DEGRADED, "Slow"))

        # Overall should be degraded (worst status)
        assert service.health.get_overall_health() == HealthStatus.DEGRADED

        # Summary should show all components
        summary = service.get_monitoring_summary()
        assert len(summary["health"]["components"]) == 3


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_monitoring_service(self):
        """Test monitoring service with no data"""
        service = MonitoringService("test")
        summary = service.get_monitoring_summary()

        assert summary["service"] == "test"
        assert summary["uptime_seconds"] >= 0
        assert len(summary["metrics"]["counters"]) == 0
        assert len(summary["metrics"]["gauges"]) == 0

    def test_metrics_with_none_labels(self):
        """Test metrics with None labels"""
        collector = MetricsCollector()
        collector.increment_counter("test", labels=None)
        collector.increment_counter("test", labels=None)

        assert collector.get_counter("test", None) == 2.0

    def test_large_histogram_values(self):
        """Test histogram with large values"""
        collector = MetricsCollector()

        for i in range(10000):
            collector.observe_histogram("test", float(i))

        stats = collector.get_histogram_stats("test")
        assert stats["count"] == 10000
        assert stats["min"] == 0.0
        assert stats["max"] == 9999.0

    def test_negative_metric_values(self):
        """Test metrics with negative values"""
        collector = MetricsCollector()
        collector.set_gauge("temperature", -10.5)

        assert collector.get_gauge("temperature") == -10.5

    def test_zero_values(self):
        """Test metrics with zero values"""
        collector = MetricsCollector()
        collector.increment_counter("test", value=0.0)
        collector.set_gauge("test_gauge", 0.0)
        collector.observe_histogram("test_hist", 0.0)

        assert collector.get_counter("test") == 0.0
        assert collector.get_gauge("test_gauge") == 0.0
        stats = collector.get_histogram_stats("test_hist")
        assert stats["avg"] == 0.0
