# src/interfaces/api/submission_api.py
import logging

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from connectors.models.assignment_config import AssignmentConfig
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


# --- Setup robust logging ---
# Configure logger to print messages to the console.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


# src/interfaces/api/submission_api.py

@app.post("/grade_submission/")
async def grade_submission_endpoint(
        submission_files: List[UploadFile] = File(..., description="The student's source code files (HTML, CSS, JS)"),
        grading_preset: str = Form(..., description="The grading preset to use (e.g., api, html, python, etc.) or custom for custom configuration"),
        student_name: str = Form(..., description="The name of the student"),
        student_credentials: str = Form(..., description="The credentials of the student (e.g., GitHub token)"),
        feedback_type: Optional[str] = Form("default", description="The type of feedback to provide (default or ai)"),
        test_files: Optional[List[UploadFile]] = File(None,description="Test Files for the submission (in case of custom preset)"),
        criteria_json: Optional[UploadFile] = File(None, description="JSON file with grading criteria (in case of custom preset)"),
        feedback_json: Optional[UploadFile] = File(None, description="JSON file with feedback configuration (in case of custom preset)"),
        ai_feedback_json: Optional[UploadFile] = File(None, description="JSON file with AI feedback configuration (in case of custom preset)"),
        setup_json: Optional[UploadFile] = File(None, description="JSON file with commands configuration (in case of custom preset)"),
        test_framework: Optional[str] = Form("custom", description="The test framework to use (e.g., pytest)"),
        openai_key: Optional[str] = Form(None, description="OpenAI API key for AI feedback"),
        redis_url: Optional[str] = Form(None, description="Redis URL for AI feedback"),
        redis_token: Optional[str] = Form(None, description="Redis token for AI feedback"),
):
    try:
        logging.info("Received API request to grade submission.")
        adapter = ApiAdapter()
        if grading_preset == "custom":
            logging.info("Custom grading preset selected. Loading custom configuration.")
            assignment_config = await adapter.create_custom_assignment_config(test_files, criteria_json, feedback_json, ai_feedback= ai_feedback_json,setup=setup_json,test_framework=test_framework)
            logging.info("Custom grading preset loaded.")
        else:
            logging.info(f"Using preset: {grading_preset}. Loading preset configuration.")
            assignment_config = AssignmentConfig.load_preset(grading_preset)
            logging.info(f"Preset {grading_preset} loaded successfully.")

        logging.info(f"Creating autograder request....")
        await adapter.create_request(submission_files=submission_files,
                               assignment_config=assignment_config,
                               student_name=student_name,
                               student_credentials=student_credentials,
                               feedback_mode=feedback_type,
                               openai_key=openai_key,
                               redis_url=redis_url,
                               redis_token=redis_token)
        logging.info(f"Autograder request created successfully.")


        # 3. Run the autograder and await its completion (asynchronous)
        logging.info("Running the autograder...")
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