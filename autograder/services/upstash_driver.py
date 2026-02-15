import json
import os
from dotenv import load_dotenv
from upstash_redis import Redis

load_dotenv() #TODO: place this in application startup
class UpstashDriver:
    def __init__(self):
        self.redis = Redis(
            os.getenv("UPSTASH_REDIS_URL"),
            os.getenv("UPSTASH_REDIS_TOKEN") # should it do it? should it remain expecting the Redis python object?
        )

    def get_user_quota(self,user_credentials: str) -> int:
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
        print(f"User '{username}' created.")

    def set_score(self, username: str, score: float):
        """Function to set the score of a user"""
        key = f"user:{username}"
        self.redis.hset(key, "score", score)
        print(f"Score '{score}' set for user '{username}'.")

