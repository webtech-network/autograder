"""Run the private control API: one process, one worker, loopback by default.

Handles live in this process's memory, so never add workers or replicas behind
a load balancer. Uvicorn owns SIGINT/SIGTERM and runs the application lifespan,
which shuts the sandbox manager down.
"""
import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "sandbox_manager.api:app",
        host=os.getenv("SANDBOX_HOST", "127.0.0.1"),
        port=int(os.getenv("SANDBOX_PORT", "8001")),
        workers=1,
    )
