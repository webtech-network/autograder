# GitHub Module

Module responsible for providing **Autograder** as a [_GitHub Action_](https://docs.github.com/en/actions), enabling its broad usage in [_GitHub Classroom_](https://classroom.github.com/).

## Goal

Interact with the student's repository to obtain: the code they produced and the gradding criteria. Then, use Autograder to generate the appropriate evaluation for the submitted contents. Finally, notify the student and GitHub Classroom about the evaluation performed and its corresponding result.

## Architecture

Adapted to GitHub Actions' execution model to allow running the code with proper access to the repository provided by GitHub Classroom.

In short, the adopted solution consists of running a Docker container with the data from the repository that triggered the Action and, with those inputs, running Autograder to provide feedback to the student in their own repository.

## Flow

1. [Action.yml](https://github.com/webtech-network/autograder/blob/main/action.yml)
   Defines the inputs received by the action, describes the output as a JSON evaluation, and runs the container with the received data as environment variables.

2. [Dockerfile](https://github.com/webtech-network/autograder/blob/main/Dockerfile.actions)
   Builds the container that installs the Autograder repository and sets [Entrypoint.sh](https://github.com/webtech-network/autograder/blob/main/github_action/entrypoint.sh) as the script to be executed when the container starts.

3. [Entrypoint.sh](https://github.com/webtech-network/autograder/blob/main/github_action/entrypoint.sh)
   Validates that the required environment variables are present and executes [main.py](https://github.com/webtech-network/autograder/blob/main/github_action/main.py) with the received data passed as CLI arguments.

4. [main.py](https://github.com/webtech-network/autograder/blob/main/github_action/main.py)
   Validates arguments, captures errors, and manipulates variables to run [github_action_service.py](https://github.com/webtech-network/autograder/blob/main/github_action/github_action_service.py) correctly in order to obtain and send the results.

5. [github_action_service.py](https://github.com/webtech-network/autograder/blob/main/github_action/github_action_service.py)
   Implements the underlying details based on Autograder's methods and the GitHub library to execute the logical procedures.

## Local testing

Done via Docker to walk through the execution flow using mocked values to replace the data coming from GitHub Classroom. For that, you need to:

- Switch to the `temp/173-github_module_tests` branch
- [Install Docker](https://docs.docker.com/get-started/get-docker/)
- Open a terminal at the project's root folder
- Run the following command:

```bash
docker build -t autograder_action -f github_action/Dockerfile.actions . && \
docker run --rm --env-file github_action/.env  autograder_action ; \
docker image rm autograder_action
```

> Add "sudo" at the beginning of each of these lines if you use "bash script" (or similar) and your terminal does not have the required permissions.

## Additional explanations

### Submission

Created with the student's data and the files submitted by the student. Required to run Autograder.

### Notify result

Uses the GitHub library to interact with the repository where Autograder is running, in the end, committing an explanatory report and notifying GitHub Classroom.
