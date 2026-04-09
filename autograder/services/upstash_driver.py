import json
import logging
from typing import Optional
from upstash_redis import Redis

from autograder.models.abstract.exporter import Exporter

logger = logging.getLogger(__name__)


class UpstashDriver(Exporter):
    def __init__(self, redis_url: str, redis_token: str):
        """Initialize the driver with explicit credentials."""
        if not redis_url or not redis_token:
            raise ValueError("UpstashDriver requires both redis_url and redis_token.")
        
        self.redis = Redis(redis_url, redis_token)

    def get_user_quota(self, user_credentials: str) -> int:
        """Function to get the quota of a user based on his username"""
        key = f"user:{user_credentials}"
        result = self.redis.hget(key, "quota")
        if result is None:
            raise Exception("User not found.")
        return int(result)

    def decrement_user_quota(self,user_credentials: str) -> bool:
        """Function to decrement the quota of a user based on his username"""
        key = f"user:{user_credentials}"

        current_quota = self.redis.hget(key, "quota")
        if current_quota is None:
            return False

        quota = int(current_quota)

        if quota <= 0:
            return False

        # Decrease and store updated quota
        self.redis.hincrby(key, "quota", -1)
        return True

    def user_exists(self, username: str) -> bool:
        key = f"user:{username}"
        result = self.redis.exists(key)
        return result > 0

    def create_user(self, username: str):
        """Function to create a new user"""
        key = f"user:{username}"
        # Cria o hash com os campos iniciais
        self.redis.hmset(key, {
            "quota": 10,
            "score": -1.0
        })
        logger.info("User '%s' created.", username)

    def set_score(self, username: str, score: float):
        """Function to set the score of a user"""
        key = f"user:{username}"
        self.redis.hset(key, "score", score)
        logger.info("Score '%s' set for user '%s'.", score, username)

    def export(self, user_id: str, score: float, feedback: Optional[str] = None) -> None:
        """Export score to Upstash Redis. Feedback is not stored."""
        self.set_score(user_id, score)

