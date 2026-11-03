"""Run the private sandbox control API in exactly one worker process.

Handles live in process memory, so this entry point always uses one worker.
It binds to 127.0.0.1 unless SANDBOX_HOST says otherwise (Compose sets 0.0.0.0
on its internal network and publishes no port).
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
