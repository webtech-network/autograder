# src/interfaces/api/submission_api.py
import logging

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from connectors.models.assignment_config import AssignmentConfig
import uvicorn

from connectors.adapters.api.api_adapter import ApiAdapter
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

@app.post("/grade_submission")
async def grade_submission_endpoint(
        submission_files: List[UploadFile] = File(..., description="The student's source code files (HTML, CSS, JS)"),
        template_preset: str = Form(..., description="The grading preset to use (e.g., api, html, python, etc.) or custom for custom configuration"),
        student_name: str = Form(..., description="The name of the student"),
        student_credentials: str = Form(..., description="The credentials of the student (e.g., GitHub token)"),
        include_feedback: bool = Form(..., description="Whether to include detailed feedback in the response"),
        criteria_json: UploadFile = File(..., description="JSON file with grading criteria (in case of custom preset)"),
        feedback_type: Optional[str] = Form("default", description="The type of feedback to provide (default or ai)"),
        custom_template: Optional[UploadFile] = File(None,description="A python file with custom tests that follows the template structure (in case of custom preset)"),
        feedback_json: Optional[UploadFile] = File(None, description="JSON file with feedback configuration (in case of custom preset)"),
        setup_json: Optional[UploadFile] = File(None, description="JSON file with commands configuration (in case of custom preset)"),
        openai_key: Optional[str] = Form(None, description="OpenAI API key for AI feedback"),
        redis_url: Optional[str] = Form(None, description="Redis URL for AI feedback"),
        redis_token: Optional[str] = Form(None, description="Redis token for AI feedback"),
):
    try:
        logging.info("Received API request to grade submission.")
        adapter = ApiAdapter()
        if template_preset == "custom":
            # Handles custom template
            if not custom_template:
                raise HTTPException(status_code=400, detail="Custom template file not given.")
            assignment_config = await adapter.load_assignment_config(template="custom",criteria=criteria_json,feedback=feedback_json,setup = setup_json, custom_template=custom_template)
        else:
            logging.info(f"Using preset: {template_preset}. Loading template preset configuration.")
            assignment_config = await adapter.load_assignment_config(template=template_preset, criteria=criteria_json, feedback=feedback_json, setup=setup_json)
            logging.info(f"Preset {template_preset} loaded successfully.")

        logging.info(f"Creating autograder request....")
        await adapter.create_request(submission_files=submission_files,
                               assignment_config=assignment_config,
                               student_name=student_name,
                               student_credentials=student_credentials,
                               include_feedback=include_feedback,
                               feedback_mode=feedback_type,
                               openai_key=openai_key,
                               redis_url=redis_url,
                               redis_token=redis_token)
        logging.info(f"Autograder request created successfully.")


        # 3. Run the autograder and await its completion (asynchronous)
        logging.info("Running the autograder...")
        adapter.run_autograder()


        # 4. Get the results from the adapter (synchronous)
        result = adapter.export_results()
        return result

    except ValueError as e:
        logging.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail="Invalid request. Please check your input parameters.")
    except FileNotFoundError as e:
        logging.error(f"File not found: {e}")
        raise HTTPException(status_code=404, detail="Required file not found.")
    except Exception as e:
        logging.exception(f"Unexpected error in grade_submission: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred while processing your submission.")

@app.get("/templates/{template_name}")
async def get_template_info(
    template_name: str,
    details_level: str = Query(
        None,
        description="Level of detail: 'summary', 'test_names'"
    ),
    test_name: str = Query(
        None,
        description="Return full details for a specific test"
    ),
):
    try:
        adapter = ApiAdapter()
        template = adapter.get_template_info(template_name.replace("_", " "))

        # Return full details of a specific test
        if test_name:
            matching_test = next(
                (t for t in template.get("tests", []) if t["name"] == test_name),
                None
            )
            if not matching_test:
                raise ValueError(f"Test '{test_name}' not found in template '{template_name}'")
            return matching_test

        # Return only template details
        if details_level == "summary":
            return {
                "template_name": template.get("template_name"),
                "template_description": template.get("template_description")
            }

        # Return only test names
        if details_level == "test_names":
            tests_list = [
                {"name": t["name"]}
                for t in template.get("tests", [])
            ]
            return {"tests": tests_list}

        # Return full template
        return template

    except ValueError as e:
        logging.error(f"Template not found: {e}")
        raise HTTPException(status_code=404, detail="Template or test not found.")
    except Exception as e:
        logging.exception(f"Error retrieving template info: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while retrieving template information.")

@app.get("/health")
def health_check():
    return {"status": "healthy"}


# To run this API service:
# uvicorn submission_api:app --host 0.0.0.0 --port 8000 --reload

if __name__ == "__main__":
    # Run the API service with Uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
