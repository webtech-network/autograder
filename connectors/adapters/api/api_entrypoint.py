# src/interfaces/api/submission_api.py
import os

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from typing import List, Optional
import uvicorn

from api_adapter import ApiAdapter

# Initialize the FastAPI app
app = FastAPI(
    title="WebTech Autograder API Service",
    description="API for submitting student assignments for automated grading.",
    version="1.0.0"
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

@app.post("/grade_submission/")
async def grade_submission_endpoint(
    test_framework: str = Form(..., description="The test framework to use (e.g., pytest)"),
    grading_preset: str = Form(..., description="The grading preset to use (e.g., api, html, python, etc.)"),
    student_name: str = Form(..., description="The name of the student"),
    student_credentials: str = Form(..., description="The credentials of the student (e.g., GitHub token)"),
    feedback_type: str = Form("default", description="The type of feedback to provide (default or ai)"),
    openai_key: Optional[str] = Form(None, description="OpenAI API key for AI feedback"),
    redis_url: Optional[str] = Form(None, description="Redis URL for AI feedback"),
    redis_token: Optional[str] = Form(None, description="Redis token for AI feedback"),
):
    """
    Receives a student's assignment submission and triggers the autograding process.
    Files are uploaded via multipart/form-data.
    """
    #logger.info(f"API Request received for student: {student_id}, assignment: {assignment_id}")
    try:
        # Call the adapter's workflow method
        result = await ApiAdapter.create(
            test_framework=test_framework,
            grading_preset=grading_preset,
            student_name=student_name,
            student_credentials=student_credentials,
            feedback_type=feedback_type,
            openai_key=openai_key,
            redis_url=redis_url,
            redis_token=redis_token
        ).run_autograder().export_results()
        return result
    except Exception as e:
        #logger.error(f"API endpoint error for {student_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")

# To run this API service:
# uvicorn submission_api:app --host 0.0.0.0 --port 8000 --reload