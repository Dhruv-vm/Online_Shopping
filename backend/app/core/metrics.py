from __future__ import annotations

import re
import threading
from typing import Any

DEFAULT_HISTOGRAM_BUCKETS: tuple[float, ...] = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
)

# Regular expressions for path normalization to prevent high cardinality
UUID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE
)
INT_PATTERN = re.compile(r"/\d+(?=/|$)")


def normalize_metric_path(path: str) -> str:
    """Normalize path parameters to bounded templates (e.g. /orders/{id})."""
    p = UUID_PATTERN.sub("{id}", path)
    p = INT_PATTERN.sub("/{id}", p)
    # Strip trailing slash if not root
    if len(p) > 1 and p.endswith("/"):
        p = p[:-1]
    return p


class Counter:
    """Prometheus monotonic counter metric."""

    def __init__(
        self, name: str, description: str, label_names: tuple[str, ...]
    ) -> None:
        self.name = name
        self.description = description
        self.label_names = label_names
        self._values: dict[tuple[str, ...], float] = {}
        self._lock = threading.Lock()

    def inc(self, value: float = 1.0, **labels: Any) -> None:
        if value < 0:
            raise ValueError("Counters can only be incremented by non-negative values")
        key = tuple(str(labels.get(k, "")) for k in self.label_names)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + value

    def get(self, **labels: Any) -> float:
        key = tuple(str(labels.get(k, "")) for k in self.label_names)
        with self._lock:
            return self._values.get(key, 0.0)

    def collect(self) -> list[str]:
        lines = [
            f"# HELP {self.name} {self.description}",
            f"# TYPE {self.name} counter",
        ]
        with self._lock:
            if not self._values:
                if not self.label_names:
                    lines.append(f"{self.name} 0.0")
                return lines
            for key, val in sorted(self._values.items()):
                if self.label_names:
                    label_str = ",".join(
                        f'{name}="{v}"'
                        for name, v in zip(self.label_names, key, strict=True)
                    )
                    lines.append(f"{self.name}{{{label_str}}} {val}")
                else:
                    lines.append(f"{self.name} {val}")
        return lines


class Gauge:
    """Prometheus gauge metric that can go up and down."""

    def __init__(
        self, name: str, description: str, label_names: tuple[str, ...]
    ) -> None:
        self.name = name
        self.description = description
        self.label_names = label_names
        self._values: dict[tuple[str, ...], float] = {}
        self._lock = threading.Lock()

    def set(self, value: float, **labels: Any) -> None:
        key = tuple(str(labels.get(k, "")) for k in self.label_names)
        with self._lock:
            self._values[key] = float(value)

    def inc(self, value: float = 1.0, **labels: Any) -> None:
        key = tuple(str(labels.get(k, "")) for k in self.label_names)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + float(value)

    def dec(self, value: float = 1.0, **labels: Any) -> None:
        key = tuple(str(labels.get(k, "")) for k in self.label_names)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) - float(value)

    def get(self, **labels: Any) -> float:
        key = tuple(str(labels.get(k, "")) for k in self.label_names)
        with self._lock:
            return self._values.get(key, 0.0)

    def collect(self) -> list[str]:
        lines = [
            f"# HELP {self.name} {self.description}",
            f"# TYPE {self.name} gauge",
        ]
        with self._lock:
            if not self._values:
                if not self.label_names:
                    lines.append(f"{self.name} 0.0")
                return lines
            for key, val in sorted(self._values.items()):
                if self.label_names:
                    label_str = ",".join(
                        f'{name}="{v}"'
                        for name, v in zip(self.label_names, key, strict=True)
                    )
                    lines.append(f"{self.name}{{{label_str}}} {val}")
                else:
                    lines.append(f"{self.name} {val}")
        return lines


class Histogram:
    """Prometheus cumulative histogram metric."""

    def __init__(
        self,
        name: str,
        description: str,
        label_names: tuple[str, ...],
        buckets: tuple[float, ...] = DEFAULT_HISTOGRAM_BUCKETS,
    ) -> None:
        self.name = name
        self.description = description
        self.label_names = label_names
        self.buckets = sorted(buckets)
        self._counts: dict[tuple[str, ...], dict[float, int]] = {}
        self._sums: dict[tuple[str, ...], float] = {}
        self._total_counts: dict[tuple[str, ...], int] = {}
        self._lock = threading.Lock()

    def observe(self, value: float, **labels: Any) -> None:
        key = tuple(str(labels.get(k, "")) for k in self.label_names)
        with self._lock:
            if key not in self._counts:
                self._counts[key] = dict.fromkeys(self.buckets, 0)
                self._sums[key] = 0.0
                self._total_counts[key] = 0

            self._sums[key] += float(value)
            self._total_counts[key] += 1
            for b in self.buckets:
                if value <= b:
                    self._counts[key][b] += 1

    def collect(self) -> list[str]:
        lines = [
            f"# HELP {self.name} {self.description}",
            f"# TYPE {self.name} histogram",
        ]
        with self._lock:
            for key, b_counts in sorted(self._counts.items()):
                label_prefix = ""
                if self.label_names:
                    label_prefix = ",".join(
                        f'{name}="{v}"'
                        for name, v in zip(self.label_names, key, strict=True)
                    )

                for b in self.buckets:
                    cnt = b_counts[b]
                    lb = f'{label_prefix},le="{b}"' if label_prefix else f'le="{b}"'
                    lines.append(f"{self.name}_bucket{{{lb}}} {cnt}")

                inf_lb = f'{label_prefix},le="+Inf"' if label_prefix else 'le="+Inf"'
                total = self._total_counts[key]
                lines.append(f"{self.name}_bucket{{{inf_lb}}} {total}")

                sum_lb = f"{{{label_prefix}}}" if label_prefix else ""
                lines.append(f"{self.name}_sum{sum_lb} {self._sums[key]}")
                lines.append(f"{self.name}_count{sum_lb} {total}")
        return lines


class MetricsRegistry:
    """Thread-safe in-memory Prometheus metrics registry."""

    def __init__(self) -> None:
        self._metrics: dict[str, Any] = {}
        self._lock = threading.Lock()

    def counter(
        self, name: str, description: str, label_names: tuple[str, ...] = ()
    ) -> Counter:
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = Counter(name, description, label_names)
            return self._metrics[name]

    def gauge(
        self, name: str, description: str, label_names: tuple[str, ...] = ()
    ) -> Gauge:
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = Gauge(name, description, label_names)
            return self._metrics[name]

    def histogram(
        self,
        name: str,
        description: str,
        label_names: tuple[str, ...] = (),
        buckets: tuple[float, ...] = DEFAULT_HISTOGRAM_BUCKETS,
    ) -> Histogram:
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = Histogram(
                    name, description, label_names, buckets=buckets
                )
            return self._metrics[name]

    def exposition(self) -> str:
        """Produce standard Prometheus 0.0.4 text output."""
        output_lines: list[str] = []
        with self._lock:
            for _, metric in sorted(self._metrics.items()):
                output_lines.extend(metric.collect())
        return "\n".join(output_lines) + "\n"

    def clear(self) -> None:
        """Clear all metric records (for test isolation)."""
        with self._lock:
            self._metrics.clear()


# Canonical Platform Metrics Registry
REGISTRY = MetricsRegistry()

# HTTP & API Metrics
http_requests_total = REGISTRY.counter(
    "http_requests_total",
    "Total HTTP requests received",
    label_names=("method", "path", "status"),
)
http_request_duration_seconds = REGISTRY.histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    label_names=("method", "path"),
)

# Kafka Publisher & Consumer Metrics
kafka_events_published_total = REGISTRY.counter(
    "kafka_events_published_total",
    "Total domain events published to Kafka topics",
    label_names=("topic", "status"),
)
consumer_events_processed_total = REGISTRY.counter(
    "consumer_events_processed_total",
    "Total Kafka consumer events processed",
    label_names=("consumer_group", "event_type", "status"),
)
consumer_duplicates_total = REGISTRY.counter(
    "consumer_duplicates_total",
    "Total duplicate events detected by consumer inbox",
    label_names=("consumer_group", "event_type"),
)
consumer_retries_total = REGISTRY.counter(
    "consumer_retries_total",
    "Total event consumption retries scheduled",
    label_names=("consumer_group", "event_type"),
)
dlq_events_routed_total = REGISTRY.counter(
    "dlq_events_routed_total",
    "Total poison or exhausted events routed to Dead-Letter Queue",
    label_names=("consumer_group", "topic", "reason"),
)

# Search & OpenSearch Metrics
search_requests_total = REGISTRY.counter(
    "search_requests_total",
    "Total product search queries executed",
    label_names=("engine", "status"),
)
search_duration_seconds = REGISTRY.histogram(
    "search_duration_seconds",
    "Product search latency in seconds",
    label_names=("engine",),
)
search_fallback_total = REGISTRY.counter(
    "search_fallback_total",
    "Total searches falling back to PostgreSQL",
    label_names=("reason",),
)
opensearch_indexing_failures_total = REGISTRY.counter(
    "opensearch_indexing_failures_total",
    "Total document indexing failures in OpenSearch",
    label_names=("index", "reason"),
)
opensearch_indexing_duration_seconds = REGISTRY.histogram(
    "opensearch_indexing_duration_seconds",
    "Time taken to index document in OpenSearch",
    label_names=("index",),
)

# Operational & System Gauges
outbox_pending_events_count = REGISTRY.gauge(
    "outbox_pending_events_count",
    "Current number of pending outbox events awaiting publication",
)
outbox_oldest_event_age_seconds = REGISTRY.gauge(
    "outbox_oldest_event_age_seconds",
    "Age in seconds of the oldest un-published outbox event",
)
circuit_breaker_state = REGISTRY.gauge(
    "circuit_breaker_state",
    "OpenSearch circuit breaker state (0=CLOSED, 1=HALF_OPEN, 2=OPEN)",
    label_names=("name",),
)
db_pool_active_connections = REGISTRY.gauge(
    "db_pool_active_connections",
    "Number of active PostgreSQL pool connections",
)
