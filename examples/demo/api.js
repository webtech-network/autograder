/* API Operations Page Logic */

async function healthCheck() {
    const result = await apiCall('/api/v1/health');
    displayResponse(result);
}

async function readyCheck() {
    const result = await apiCall('/api/v1/ready');
    displayResponse(result);
}

async function listTemplates() {
    const result = await apiCall('/api/v1/templates');
    displayResponse(result);
}

async function getTemplate() {
    const templateName = document.getElementById('templateName').value;

    if (!templateName) {
        alert('Please enter a template name');
        return;
    }

    const result = await apiCall(`/api/v1/templates/${templateName}`);
    displayResponse(result);
}

async function listConfigs() {
    const result = await apiCall('/api/v1/configs');
    displayResponse(result);
}

async function getConfig() {
    const assignmentId = document.getElementById('configAssignmentId').value;

    if (!assignmentId) {
        alert('Please enter an assignment ID');
        return;
    }

    const result = await apiCall(`/api/v1/configs/${assignmentId}`);
    displayResponse(result);
}

async function updateConfig() {
    const configId = document.getElementById('configId').value;

    if (!configId) {
        alert('Please enter a config ID');
        return;
    }

    // Example update payload
    const payload = {
        criteria: {
            test_library: "input_output",
            base: {
                weight: 100,
                tests: [
                    {
                        name: "expect_output",
                        parameters: [
                            { name: "inputs", value: ["5", "3"] },
                            { name: "expected_output", value: "8" },
                            { name: "program_command", value: "python calculator.py" }
                        ]
                    }
                ]
            }
        }
    };

    const result = await apiCall(`/api/v1/configs/${configId}`, 'PUT', payload);
    displayResponse(result);
}

async function getSubmission() {
    const submissionId = document.getElementById('submissionId').value;

    if (!submissionId) {
        alert('Please enter a submission ID');
        return;
    }

    const result = await apiCall(`/api/v1/submissions/${submissionId}`);
    displayResponse(result);
}

async function getUserSubmissions() {
    const userId = document.getElementById('apiUserId').value;

    if (!userId) {
        alert('Please enter a user ID');
        return;
    }

    const result = await apiCall(`/api/v1/submissions?user_id=${userId}`);
    displayResponse(result);
}

