import json
import os
from dotenv import load_dotenv
from upstash_redis import Redis

load_dotenv()

redis = Redis(
    url=os.environ["UPSTASH_REDIS_REST_URL"],
    token=os.environ["UPSTASH_REDIS_REST_TOKEN"]

)

def token_exists(token: str) -> bool:
    """Function to check if a given token exists in the database"""
    key = f"token:{token}"
    result = redis.get(key)
    return result is not None

def create_token(token: str, quota: int = 10):
    """Function to create a new token"""
    key = f"token:{token}"
    value = {"token": token, "quota": quota}
    redis.set(key, json.dumps(value))
    print(f"✅ Token '{token}' created with quota {quota}")

def get_token_quota(token: str) -> int:
    """Function to get the quota of a user based on his token"""
    key = f"token:{token}"
    result = redis.get(key)
    if result is None:
        raise Exception("Token not found.")
    return json.loads(result)["quota"]

def decrement_token_quota(token: str) -> tuple[bool, int]:
    """Function to decrement the quota of a user based on his token"""
    key = f"token:{token}"
    result = redis.get(key)
    if result is None:
        return False, 0

    data = json.loads(result)
    quota = data.get("quota", 0)

    if quota <= 0:
        return False, 0

    # Decrease and store updated quota
    data["quota"] = quota - 1
    redis.set(key, json.dumps(data))
    return True, data["quota"]



# Usage test:

token = "ghp_test123"

# Check and create if missing
if not token_exists(token):
    create_token(token)

# Decrement quota
allowed, remaining = decrement_token_quota(token)
if allowed:
    print(f"✅ Allowed. Remaining quota: {remaining}")
else:
    print("🚫 Too many requests. Quota exhausted.")
