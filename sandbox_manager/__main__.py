import uvicorn
import os

if __name__ == "__main__":
    port = int(os.getenv("SANDBOX_PORT", "8001"))
    host = os.getenv("SANDBOX_HOST", "0.0.0.0")
    
    # We use sandbox_manager.api:app to allow hot reload if needed
    uvicorn.run(
        "sandbox_manager.api:app",
        host=host,
        port=port,
        reload=os.getenv("APP_ENV", "local") == "local"
    )
