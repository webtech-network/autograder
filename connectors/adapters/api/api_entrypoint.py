# src/interfaces/api/submission_api.py
import os

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from connectors.utils.load_preset import load_preset
import uvicorn

from api_adapter import ApiAdapter

# Initialize the FastAPI app
app = FastAPI(
    title="WebTech Autograder API Service",
    description="API for submitting student assignments for automated grading.",
    version="1.0.0"
)

# 2. DEFINE THE ALLOWED ORIGINS
# These are the URLs where your frontend is running.
# For local development, this often includes localhost on various ports
# or the file protocol if you open the HTML directly in the browser.
origins = ["*"]

# ADD THE MIDDLEWARE TO YOUR APP
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency to provide the ApiAdapter instance
# This allows injecting configuration (like Redis/OpenAI keys)
# For a real deployment, these would come from environment variables or a config file
def get_api_adapter() -> ApiAdapter:
    # In a production environment, these would be loaded from environment variables
    # or a secure configuration management system.
    redis_name = os.getenv("REDIS_NAME", "default_redis_name")
    redis_url = os.getenv("REDIS_URL", "http://localhost:8080")
    openai_key = os.getenv("OPENAI_API_KEY", "dummy_openai_key")
    #return ApiAdapter(redis_name=redis_name, redis_url=redis_url, openai_key=openai_key)


# src/interfaces/api/submission_api.py

@app.post("/grade_submission/")
async def grade_submission_endpoint(
        files: List[UploadFile] = File(..., description="The student's source code files (HTML, CSS, JS)"),
        test_framework: str = Form(..., description="The test framework to use (e.g., pytest)"),
        grading_preset: str = Form(..., description="The grading preset to use (e.g., api, html, python, etc.)"),
        student_name: str = Form(..., description="The name of the student"),
        student_credentials: str = Form(..., description="The credentials of the student (e.g., GitHub token)"),
        feedback_type: str = Form("default", description="The type of feedback to provide (default or ai)"),
        openai_key: Optional[str] = Form(None, description="OpenAI API key for AI feedback"),
        redis_url: Optional[str] = Form(None, description="Redis URL for AI feedback"),
        redis_token: Optional[str] = Form(None, description="Redis token for AI feedback"),
):
    try:
        # 1. Create the adapter instance (synchronous)
        adapter = ApiAdapter.create(
            test_framework=test_framework,
            grading_preset=grading_preset,
            student_name=student_name,
            student_credentials=student_credentials,
            feedback_type=feedback_type,
            openai_key=openai_key,
            redis_url=redis_url,
            redis_token=redis_token
        )

        # Load the grading preset configuration
        load_preset(grading_preset)
        # 2. Save the submission files (asynchronous)
        await adapter.export_submission_files(submission_files=files)

        # 3. Run the autograder and await its completion (asynchronous)
        await adapter.run_autograder()

        # 4. Get the results from the adapter (synchronous)
        result = adapter.export_results()

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")
@app.get("/presets")
def get_presets():
    """
    Returns a list of available grading presets.
    This could be extended to return more detailed information about each preset.
    """
    # For now, we return a static list of presets.
    # In a real application, this could query a database or configuration file.
    presets = [
        "html-css-js",
        "etapa-2",
        "javascript"
    ]
    return {"presets": presets}

# To run this API service:
# uvicorn submission_api:app --host 0.0.0.0 --port 8000 --reload

if __name__ == "__main__":
    # Run the API service with Uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)