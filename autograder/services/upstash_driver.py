import logging
from typing import Optional
from upstash_redis import Redis

from autograder.models.abstract.exporter import Exporter

logger = logging.getLogger(__name__)


class UpstashDriver(Exporter):
    """
    Exporter implementation that persists grading scores to Upstash Redis.

    Only the score is stored — feedback text is not written to Redis.
    Keys follow the pattern ``user:<user_id>`` with a ``score`` field.
    """

    def __init__(self, redis_url: str, redis_token: str):
        """Initialize the driver with explicit credentials."""
        if not redis_url or not redis_token:
            raise ValueError("UpstashDriver requires both redis_url and redis_token.")

        self.redis = Redis(redis_url, redis_token)

    def set_score(self, user_id: str, score: float) -> None:
        """Write the score for a user into Redis."""
        key = f"user:{user_id}"
        self.redis.hset(key, "score", score)
        logger.info("Score '%.2f' set for user '%s'.", score, user_id)

    def export(self, user_id: str, score: float, feedback: Optional[str] = None) -> None:
        """Export score to Upstash Redis. Feedback is not stored."""
        self.set_score(user_id, score)
