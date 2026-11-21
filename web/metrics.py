"""Prometheus metrics of the HTTP service: HTTP, grading pipeline, queue and database pool.

``GET /metrics`` (``web/api/metrics.py``) exposes :attr:`WebMetrics.registry`.
Labels come only from closed sets (methods, route templates, status codes,
:class:`~autograder.models.language.Language`, outcome statuses, error
categories and the published outcome error codes); a value outside its set is
reported as ``other``. Submission, attempt and user identifiers are never labels.
"""
import asyncio
from datetime import timezone
from time import monotonic, perf_counter
from typing import get_args

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.registry import Collector
from sqlalchemy import event, func, select, text
from sqlalchemy.pool import QueuePool

from autograder.models.contracts.outcome import OUTCOME_ERROR_CODES, OutcomeError
from autograder.models.language import Language
from sandbox_manager.metrics import OTHER, HttpMetrics, SandboxCollector
from web.config.logging import get_logger
from web.database.models.submission import Submission, SubmissionStatus

logger = get_logger(__name__)

LANGUAGES = frozenset(language.value for language in Language)
OUTCOME_STATUSES = frozenset({"completed", "failed"})
ERROR_CATEGORIES = frozenset(get_args(
    OutcomeError.model_fields["category"].annotation))  # pylint: disable=unsubscriptable-object  # pydantic class property
ERROR_CODES = frozenset(OUTCOME_ERROR_CODES)
#: Seconds per attempt: static checks take under a second, sandboxed runs minutes.
GRADING_BUCKETS = (0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0)
#: Seconds to open one database connection.
CONNECT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
#: A scrape gives up on the queue query after this long (Prometheus' default scrape timeout is 10 s).
QUEUE_QUERY_TIMEOUT_SECONDS = 5.0
#: Scrapes within this interval of the last queue read reuse it: at most one query per interval.
QUEUE_REFRESH_SECONDS = 5.0
QUEUE_STATES = ("pending", "processing", "retry_wait")
_CONNECT_STARTED = "autograder_metrics_connect_started"


def _closed(value, allowed) -> str:
    return value if value in allowed else OTHER


def _utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class GradingMetrics:
    """Grading throughput, failures and duration as recorded by the durable workers."""

    def __init__(self, registry: CollectorRegistry):
        self.submissions = Counter(
            "autograder_submissions", "Final grading outcomes published by this process's workers.",
            ("status", "language", "error_category"), registry=registry)
        self.failures = Counter(
            "autograder_grading_failures", "Failed grading attempts, including ones that are retried.",
            ("category", "code", "retryable"), registry=registry)
        self.duration = Histogram(
            "autograder_grading_duration_seconds",
            "Wall time of one grading attempt, from claim to outcome (includes waiting for a sandbox).",
            ("language", "status"), buckets=GRADING_BUCKETS, registry=registry)
        self.in_progress = Gauge("autograder_grading_in_progress",
                                 "Grading attempts this process is running now.", registry=registry)

    def attempt_finished(self, language: str, outcome: dict, seconds: float) -> None:
        """One attempt produced ``outcome`` (published or released for retry)."""
        status = _closed(outcome.get("status"), OUTCOME_STATUSES)
        self.duration.labels(_closed(language, LANGUAGES), status).observe(seconds)
        if status == "failed":
            error = outcome.get("error") or {}
            self.failures.labels(_closed(error.get("category"), ERROR_CATEGORIES),
                                 _closed(error.get("code"), ERROR_CODES),
                                 "true" if error.get("retryable") is True else "false").inc()

    def published(self, language: str, outcome: dict) -> None:
        """A worker published ``outcome`` as the submission's final result."""
        error = outcome.get("error") or {}
        category = _closed(error.get("category"), ERROR_CATEGORIES) if error else "none"
        self.submissions.labels(_closed(outcome.get("status"), OUTCOME_STATUSES),
                                _closed(language, LANGUAGES), category).inc()


class QueueMetrics(Collector):
    """Open submissions of the shared PostgreSQL queue (every replica reports the same values).

    Concurrent scrapes share one read and reuse it for ``QUEUE_REFRESH_SECONDS``,
    so an unauthenticated flood of ``/metrics`` requests reads the database at most
    once per interval. Each read publishes one immutable snapshot: a scrape never
    sees half-updated values. A failed or slow read reports ``autograder_queue_up 0``
    and no queue values, and is logged once per transition.
    """

    def __init__(self, *, clock=monotonic):
        self._clock = clock
        self._lock = asyncio.Lock()
        self._read_at = None
        self._snapshot = None  # (counts by state, oldest pending age in seconds) or None after a failure

    def describe(self):
        return []  # Nothing is read at registration.

    async def refresh(self, sessions) -> None:
        """Read the queue unless a read finished within ``QUEUE_REFRESH_SECONDS``."""
        async with self._lock:
            if self._read_at is not None and self._clock() - self._read_at < QUEUE_REFRESH_SECONDS:
                return
            try:
                snapshot = await asyncio.wait_for(self._read(sessions), QUEUE_QUERY_TIMEOUT_SECONDS)
            except Exception as exc:  # pylint: disable=broad-exception-caught  # a scrape never fails on the database
                if self._snapshot is not None or self._read_at is None:
                    logger.warning("metrics_queue_unavailable: %s", type(exc).__name__)
                snapshot = None
            else:
                if self._snapshot is None and self._read_at is not None:
                    logger.info("metrics_queue_available")
            self._snapshot, self._read_at = snapshot, self._clock()

    def collect(self):
        snapshot = self._snapshot
        yield GaugeMetricFamily("autograder_queue_up", "1 if the last queue read succeeded, 0 if it failed.",
                                value=0 if snapshot is None else 1)
        if snapshot is None:
            return
        counts, oldest_age = snapshot
        submissions = GaugeMetricFamily(
            "autograder_queue_submissions",
            "Open submissions: pending (never claimed), processing (an attempt holds or held it) or "
            "retry_wait (released after a retryable failure).", labels=("state",))
        for state in QUEUE_STATES:
            submissions.add_metric((state,), counts.get(state, 0))
        yield submissions
        yield GaugeMetricFamily("autograder_queue_oldest_age_seconds",
                                "Age of the oldest pending submission (0 when none is pending).", value=oldest_age)

    @staticmethod
    async def _read(sessions):
        # Only the two open statuses (indexed column), grouped: a handful of rows whatever the history size.
        # Rows without a bound definition are never claimed, so they are not queued work.
        statement = (select(Submission.status, Submission.attempt_id.is_(None), func.count(),
                            func.min(Submission.submitted_at))
                     .where(Submission.status.in_((SubmissionStatus.PENDING, SubmissionStatus.PROCESSING)),
                            Submission.definition_snapshot.is_not(None))
                     .group_by(Submission.status, Submission.attempt_id.is_(None)))
        async with sessions() as session:
            if session.get_bind().dialect.name == "postgresql":
                # Bound the statement on the server too: cancelling the client does not stop it.
                await session.execute(text(f"SET LOCAL statement_timeout = {int(QUEUE_QUERY_TIMEOUT_SECONDS * 1000)}"))
            now = _utc(await session.scalar(select(func.now())))  # The clock that stamped submitted_at.
            rows = (await session.execute(statement)).all()
            await session.rollback()
        counts, oldest = {}, None
        for status, unowned, count, first in rows:
            if status == SubmissionStatus.PENDING:
                state = "pending"
                oldest = _utc(first) if oldest is None else min(oldest, _utc(first))
            else:
                state = "retry_wait" if unowned else "processing"
            counts[state] = counts.get(state, 0) + count
        return counts, 0.0 if oldest is None else max(0.0, (now - oldest).total_seconds())


class DatabasePoolCollector(Collector):
    """Connection-pool gauges of one engine, read at scrape time (no labels: one engine per process).

    A pool without a size (``NullPool``, ``StaticPool``) yields nothing.
    """

    def __init__(self, engine):
        self._engine = engine

    def describe(self):
        return []  # Nothing is read at registration.

    def collect(self):
        pool = self._engine.sync_engine.pool  # Read each time: dispose() replaces the pool.
        if not isinstance(pool, QueuePool):
            return
        yield GaugeMetricFamily("autograder_db_pool_size", "Connections the pool keeps (pool_size).",
                                value=pool.size())
        yield GaugeMetricFamily("autograder_db_pool_checked_out", "Connections in use now.",
                                value=pool.checkedout())
        yield GaugeMetricFamily("autograder_db_pool_checked_in", "Idle connections in the pool.",
                                value=pool.checkedin())
        # overflow() counts down from -pool_size until the pool is full.
        yield GaugeMetricFamily("autograder_db_pool_overflow", "Connections open beyond pool_size.",
                                value=max(0, pool.overflow()))
        yield GaugeMetricFamily(
            "autograder_db_pool_max_overflow", "Connections allowed beyond pool_size (max_overflow).",
            value=pool._max_overflow)  # pylint: disable=protected-access  # QueuePool has no public accessor


class DatabaseMetrics:
    """Connection establishment of one engine, recorded from SQLAlchemy events, plus its pool gauges."""

    def __init__(self, registry: CollectorRegistry):
        self.registry = registry
        self.connections = Counter("autograder_db_pool_connections_created",
                                   "Database connections the pool opened.", registry=registry)
        self.connect_duration = Histogram("autograder_db_pool_connect_duration_seconds",
                                          "Time to open one database connection.",
                                          buckets=CONNECT_BUCKETS, registry=registry)

    def instrument(self, engine) -> None:
        """Register the pool gauges and connection events of ``engine`` (an ``AsyncEngine``)."""
        self.registry.register(DatabasePoolCollector(engine))
        event.listen(engine.sync_engine, "do_connect", self._connecting)
        event.listen(engine.sync_engine, "connect", self._connected)

    @staticmethod
    def _connecting(_dialect, connection_record, _cargs, _cparams):
        connection_record.info[_CONNECT_STARTED] = perf_counter()

    def _connected(self, _dbapi_connection, connection_record):
        self.connections.inc()
        started = connection_record.info.pop(_CONNECT_STARTED, None)
        if started is not None:
            self.connect_duration.observe(perf_counter() - started)


class WebMetrics:
    """Every metric of one HTTP service instance, in its own registry."""

    def __init__(self):
        self.registry = CollectorRegistry()
        self.http = HttpMetrics(self.registry)
        self.grading = GradingMetrics(self.registry)
        self.queue = QueueMetrics()
        self.registry.register(self.queue)
        self.database = DatabaseMetrics(self.registry)

    def watch_sandboxes(self, manager) -> None:
        """Report the pools of an in-process sandbox manager (``SANDBOX_MODE=local``)."""
        self.registry.register(SandboxCollector(manager))
