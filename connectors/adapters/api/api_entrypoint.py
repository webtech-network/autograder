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
    student_id: str = Form(..., description="Unique identifier for the student."),
    assignment_id: str = Form(..., description="Unique identifier for the assignment."),
    test_runner_type: str = Form(..., description="Type of test runner (e.g., 'jest-custom-tests', 'pytest-native')."),
    # Student submission files (e.g., server.js, package.json, student_code.py)
    submission_files: List[UploadFile] = File(..., description="Student's submission files."),
    # Configuration files (criteria.json, ai-feedback.json, feedback.json)
    config_files: List[UploadFile] = File(..., description="Autograder configuration files (criteria.json, ai-feedback.json, feedback.json)."),
    # Optional user-provided test files (e.g., base.test.js, test_my_feature.py)
    user_test_files: Optional[List[UploadFile]] = File(None, description="Optional custom test files provided by the user."),
    api_adapter: ApiAdapter = Depends(get_api_adapter) # Inject the adapter
):
    """
    Receives a student's assignment submission and triggers the autograding process.
    Files are uploaded via multipart/form-data.
    """
    #logger.info(f"API Request received for student: {student_id}, assignment: {assignment_id}")
    try:
        # Call the adapter's workflow method
        result = await api_adapter.run_autograding_workflow(
            student_id=student_id,
            assignment_id=assignment_id,
            test_runner_type=test_runner_type,
            submission_files=submission_files,
            config_files=config_files,
            user_test_files=user_test_files
        )
        return result
    except Exception as e:
        #logger.error(f"API endpoint error for {student_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")

# To run this API service:
# uvicorn submission_api:app --host 0.0.0.0 --port 8000 --reload