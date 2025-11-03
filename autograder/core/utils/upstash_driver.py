import json
import os
from dotenv import load_dotenv
from upstash_redis import Redis

load_dotenv()
class Driver:
    def __init__(self,redis):
        self.redis = redis

    def token_exists(self,token: str) -> bool:
        """Function to check if a given token exists in the database"""
        key = f"token:{token}"
        result = self.redis.exists(key)
        return result > 0

    def create_token(self,token: str, quota: int = 10):
        """Function to create a new token"""
        key = f"token:{token}"
        value = {"token": token, "quota": quota}
        # self.redis.set(key, json.dumps(value))
        self.redis.hmset(key, value)
        print(f"✅ Token '{token}' created with quota {quota}")

    def get_token_quota(self,token: str) -> int:
        """Function to get the quota of a user based on his token"""
        key = f"token:{token}"
        result = self.redis.hget(key, "quota")
        if result is None:
            raise Exception("Token not found.")
        return int(result)

    def decrement_token_quota(self,token: str) -> bool:
        """Function to decrement the quota of a user based on his token"""
        key = f"token:{token}"

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
            "username": username,
            "score": -1.0
        })
        print(f"User '{username}' created.")

    def set_score(self, username: str, score: float):
        """Function to set the score of a user"""
        key = f"user:{username}"
        self.redis.hset(key, "score", score)
        print(f"Score '{score}' set for user '{username}'.")

    @classmethod
    def create(cls,redis_token,redis_url):
        redis = Redis(
            url = redis_url,
            token = redis_token
        )
        return cls(redis)
