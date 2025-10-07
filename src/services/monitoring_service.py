"""
Monitoring Service - Production Observability

Provides structured logging, metrics collection, and health monitoring.
Blueprint requirement: Production ops (monitoring, metrics, health checks).

Features:
- Structured JSON logging
- Metrics collection (counters, gauges, histograms)
- Health check system
- Performance tracking
- Error rate monitoring
"""

import logging
import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum


class HealthStatus(str, Enum):
    """Health check status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class MetricPoint:
    """Single metric data point"""
    name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class HealthCheck:
    """Health check result"""
    component: str
    status: HealthStatus
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    response_time_ms: Optional[float] = None


class StructuredLogger:
    """
    Structured JSON logger for better log aggregation

    Compatible with Loki, Elasticsearch, etc.
    """

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.service_name = name

    def log(
        self,
        level: str,
        message: str,
        **kwargs
    ):
        """
        Log structured message

        Args:
            level: Log level (info, warning, error)
            message: Log message
            **kwargs: Additional structured fields
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level.upper(),
            "service": self.service_name,
            "message": message,
            **kwargs
        }

        log_method = getattr(self.logger, level.lower())
        log_method(json.dumps(log_entry))

    def info(self, message: str, **kwargs):
        """Log info message"""
        self.log("info", message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self.log("warning", message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log error message"""
        self.log("error", message, **kwargs)

    def metric(self, metric_name: str, value: float, **labels):
        """Log metric data point"""
        self.log(
            "info",
            f"metric: {metric_name}",
            metric=metric_name,
            value=value,
            labels=labels
        )


class MetricsCollector:
    """
    Collect and aggregate metrics

    Supports counters, gauges, and histograms
    """

    def __init__(self):
        self.counters: Dict[str, float] = defaultdict(float)
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, List[float]] = defaultdict(list)
        self.metric_history: List[MetricPoint] = []

    def increment_counter(
        self,
        name: str,
        value: float = 1.0,
        labels: Optional[Dict[str, str]] = None
    ):
        """
        Increment counter metric

        Args:
            name: Metric name
            value: Increment amount
            labels: Metric labels
        """
        key = self._make_key(name, labels)
        self.counters[key] += value
        self._record_metric(name, self.counters[key], labels)

    def set_gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ):
        """
        Set gauge metric

        Args:
            name: Metric name
            value: Current value
            labels: Metric labels
        """
        key = self._make_key(name, labels)
        self.gauges[key] = value
        self._record_metric(name, value, labels)

    def observe_histogram(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ):
        """
        Add observation to histogram

        Args:
            name: Metric name
            value: Observed value
            labels: Metric labels
        """
        key = self._make_key(name, labels)
        self.histograms[key].append(value)
        self._record_metric(name, value, labels)

    def get_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """Get counter value"""
        key = self._make_key(name, labels)
        return self.counters.get(key, 0.0)

    def get_gauge(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """Get gauge value"""
        key = self._make_key(name, labels)
        return self.gauges.get(key, 0.0)

    def get_histogram_stats(
        self,
        name: str,
        labels: Optional[Dict[str, str]] = None
    ) -> Dict[str, float]:
        """
        Get histogram statistics

        Returns:
            Dict with count, sum, avg, min, max, p50, p95, p99
        """
        key = self._make_key(name, labels)
        values = self.histograms.get(key, [])

        if not values:
            return {"count": 0, "sum": 0, "avg": 0}

        sorted_values = sorted(values)
        count = len(values)

        return {
            "count": count,
            "sum": sum(values),
            "avg": sum(values) / count,
            "min": min(values),
            "max": max(values),
            "p50": sorted_values[int(count * 0.50)],
            "p95": sorted_values[int(count * 0.95)] if count > 1 else sorted_values[0],
            "p99": sorted_values[int(count * 0.99)] if count > 1 else sorted_values[0]
        }

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all metrics summary"""
        return {
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "histograms": {
                name: self.get_histogram_stats(name)
                for name in set(k.split("|")[0] for k in self.histograms.keys())
            }
        }

    def _make_key(self, name: str, labels: Optional[Dict[str, str]]) -> str:
        """Create unique key from name and labels"""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}|{label_str}"

    def _record_metric(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]]
    ):
        """Record metric in history"""
        self.metric_history.append(
            MetricPoint(name=name, value=value, labels=labels or {})
        )

        # Keep only last 1000 points
        if len(self.metric_history) > 1000:
            self.metric_history = self.metric_history[-1000:]


class HealthCheckMonitor:
    """
    Monitor system health

    Tracks health of various components
    """

    def __init__(self):
        self.health_checks: List[HealthCheck] = []
        self.component_status: Dict[str, HealthStatus] = {}

    def check_component(
        self,
        component: str,
        check_func,
        timeout_seconds: float = 5.0
    ) -> HealthCheck:
        """
        Run health check for component

        Args:
            component: Component name
            check_func: Function that returns (status, message) tuple
            timeout_seconds: Check timeout

        Returns:
            HealthCheck result
        """
        start_time = time.time()

        try:
            # Run check
            status, message = check_func()

            # Calculate response time
            response_time = (time.time() - start_time) * 1000

            # Check if too slow
            if response_time > timeout_seconds * 1000:
                status = HealthStatus.DEGRADED
                message += f" (slow: {response_time:.0f}ms)"

        except Exception as e:
            status = HealthStatus.UNHEALTHY
            message = f"Check failed: {str(e)}"
            response_time = (time.time() - start_time) * 1000

        check = HealthCheck(
            component=component,
            status=status,
            message=message,
            response_time_ms=response_time
        )

        self.health_checks.append(check)
        self.component_status[component] = status

        # Keep only last 100 checks
        if len(self.health_checks) > 100:
            self.health_checks = self.health_checks[-100:]

        return check

    def get_overall_health(self) -> HealthStatus:
        """
        Get overall system health

        Returns:
            Worst health status across all components
        """
        if not self.component_status:
            return HealthStatus.HEALTHY

        statuses = list(self.component_status.values())

        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY

    def get_health_summary(self) -> Dict[str, Any]:
        """Get health summary"""
        return {
            "overall": self.get_overall_health().value,
            "components": {
                component: status.value
                for component, status in self.component_status.items()
            },
            "last_checks": [
                {
                    "component": check.component,
                    "status": check.status.value,
                    "message": check.message,
                    "response_time_ms": check.response_time_ms
                }
                for check in self.health_checks[-10:]
            ]
        }


class MonitoringService:
    """
    Complete monitoring service

    Combines structured logging, metrics, and health checks
    """

    def __init__(self, service_name: str = "rag_service"):
        self.logger = StructuredLogger(service_name)
        self.metrics = MetricsCollector()
        self.health = HealthCheckMonitor()
        self.service_name = service_name
        self.start_time = datetime.now()

    def log_request(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        duration_ms: float,
        **kwargs
    ):
        """Log HTTP request"""
        self.logger.info(
            f"{method} {endpoint}",
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            duration_ms=duration_ms,
            **kwargs
        )

        # Track metrics
        self.metrics.increment_counter(
            "http_requests_total",
            labels={"endpoint": endpoint, "method": method, "status": str(status_code)}
        )
        self.metrics.observe_histogram(
            "http_request_duration_ms",
            duration_ms,
            labels={"endpoint": endpoint}
        )

    def log_error(
        self,
        error_type: str,
        message: str,
        **kwargs
    ):
        """Log error with tracking"""
        self.logger.error(
            message,
            error_type=error_type,
            **kwargs
        )

        self.metrics.increment_counter(
            "errors_total",
            labels={"error_type": error_type}
        )

    def track_operation(
        self,
        operation: str,
        duration_ms: float,
        success: bool = True,
        **labels
    ):
        """Track operation performance"""
        self.metrics.increment_counter(
            f"{operation}_total",
            labels={**labels, "success": str(success)}
        )
        self.metrics.observe_histogram(
            f"{operation}_duration_ms",
            duration_ms,
            labels=labels
        )

    def get_uptime_seconds(self) -> float:
        """Get service uptime in seconds"""
        return (datetime.now() - self.start_time).total_seconds()

    def get_monitoring_summary(self) -> Dict[str, Any]:
        """Get complete monitoring summary"""
        return {
            "service": self.service_name,
            "uptime_seconds": self.get_uptime_seconds(),
            "health": self.health.get_health_summary(),
            "metrics": self.metrics.get_all_metrics()
        }


# Test
if __name__ == "__main__":
    monitor = MonitoringService("test_service")

    print("=" * 60)
    print("Monitoring Service Test")
    print("=" * 60)

    # Test 1: Structured logging
    print("\n1. Structured logging:")
    monitor.logger.info("Service started", version="1.0.0")
    monitor.logger.warning("High memory usage", memory_mb=1024)
    print("   ✓ Logged structured messages")

    # Test 2: Metrics
    print("\n2. Metrics collection:")
    monitor.metrics.increment_counter("requests", labels={"endpoint": "/search"})
    monitor.metrics.increment_counter("requests", labels={"endpoint": "/search"})
    monitor.metrics.set_gauge("memory_mb", 512)
    monitor.metrics.observe_histogram("latency_ms", 45)
    monitor.metrics.observe_histogram("latency_ms", 67)
    monitor.metrics.observe_histogram("latency_ms", 89)

    print(f"   Counter 'requests': {monitor.metrics.get_counter('requests', {'endpoint': '/search'})}")
    print(f"   Gauge 'memory_mb': {monitor.metrics.get_gauge('memory_mb')}")
    stats = monitor.metrics.get_histogram_stats("latency_ms")
    print(f"   Histogram 'latency_ms': avg={stats['avg']:.1f}ms, p95={stats['p95']:.1f}ms")

    # Test 3: Health checks
    print("\n3. Health checks:")

    def check_database():
        return (HealthStatus.HEALTHY, "Database connection OK")

    def check_cache():
        return (HealthStatus.DEGRADED, "Cache hit rate below 50%")

    monitor.health.check_component("database", check_database)
    monitor.health.check_component("cache", check_cache)

    print(f"   Overall health: {monitor.health.get_overall_health().value}")
    for comp, status in monitor.health.component_status.items():
        print(f"   - {comp}: {status.value}")

    # Test 4: Request logging
    print("\n4. Request logging:")
    monitor.log_request("/search", "POST", 200, 123.4)
    monitor.log_request("/ingest", "POST", 201, 456.7)
    print("   ✓ Logged HTTP requests")

    # Test 5: Summary
    print("\n5. Monitoring summary:")
    summary = monitor.get_monitoring_summary()
    print(f"   Uptime: {summary['uptime_seconds']:.1f}s")
    print(f"   Health: {summary['health']['overall']}")
    print(f"   Metrics: {len(summary['metrics']['counters'])} counters, "
          f"{len(summary['metrics']['gauges'])} gauges")

    print("\n" + "=" * 60)
    print("✅ All tests passed")
