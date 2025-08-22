# 1. Getting Started

Welcome to the Getting Started guide for the WebTech Autograder! This guide will walk you through the essential steps to configure and run your first grading session. We'll cover how to use presets and explain the role of each configuration file.

---

## How to Use Presets

Presets are pre-configured sets of tests and grading criteria for common assignments. They are the fastest way to get started with the autograder. The system comes with two built-in presets:

* **`html-css-js`**: For basic web development assignments.
* **`etapa-2`**: A more complex preset for a specific multi-stage project involving a Node.js API.

To use a preset, you simply need to specify its name when running the autograder (e.g., through the GitHub Action or the API).

---

## Anatomy of a Preset

Each preset is a directory that contains all the necessary files to run a grading session. Here's a breakdown of the files you'll find in a typical preset and what they do:

### The `tests/` Folder

This folder contains the test suites that will be run against the student's submission.

* **`test_base.py` / `test_base.js`**: This file contains the **mandatory** tests for the assignment. These are the core requirements that a student must meet to pass.
* **`test_bonus.py` / `test_bonus.js`**: This file contains tests for **optional** features or requirements. Passing these tests will add points to the student's score, but they are not required to pass the assignment.
* **`test_penalty.py` / `test_penalty.js`**: This file contains tests that check for things that are **forbidden** in the assignment. If a student's submission passes any of these tests, points will be deducted from their score.

### `criteria.json`

This file defines the grading criteria for the assignment. It's where you specify how the tests are grouped into subjects and how much each subject is worth.

* **`weight`**: The total weight of the test suite (e.g., `base`, `bonus`, or `penalty`).
* **`subjects`**: An object that defines the different subjects within the test suite. Each subject has its own `weight` and a `test_path` that is used to identify the tests that belong to it.

### `feedback.json`

This file allows you to provide custom feedback messages for each test. For each test, you can specify a message for both the "pass" and "fail" cases. This is a great way to give students targeted feedback that helps them understand their mistakes.

### `ai-feedback.json`

This file is used to configure the AI-powered feedback feature. It contains prompts and other settings that guide the AI in generating helpful and human-like feedback for students.

* **`prompts`**: Contains the `system_prompt`, `assignment_context`, and `extra_orientations` that the AI will use to generate the feedback.
* **`submission_files`**: A list of the student's files that the AI should analyze.
* **`learning_resources`**: A list of URLs and descriptions of learning resources that the AI can recommend to students.

### `autograder-setup.json`

This file allows you to specify commands that should be run before the tests are executed. This is useful for installing dependencies, setting up a database, or starting a server.

* **`commands`**: A list of commands to be executed. Each command has a `name`, the `command` itself, and an optional `background` flag.
* **`file_checks`**: A list of files that must be present in the student's submission for the tests to run.

---

## Running the Autograder

To run a grading session, you need to provide a set of required parameters, either through the GitHub Actions environment or the API.

### Required Parameters

* **`grading_preset`**: The name of the preset to use (e.g., `html-css-js`).
* **`feedback-type`**: The type of feedback to generate. See **Feedback Modes** below for more details.

### Feedback Modes

The autograder supports two feedback modes:

* **`default`**: This mode generates a feedback report based on the messages defined in the `feedback.json` file.
* **`ai`**: This is an **optional** mode that uses an AI model to generate more detailed and personalized feedback. If you choose this mode, you must provide the following:
    * An **`ai-feedback.json`** file in your preset.
    * An **`openai_key`** for accessing the OpenAI API.
    * A **`redis_token`** and **`redis_url`** for caching and managing AI usage quotas.

---

## Recommended Practices

* **Start with a Preset**: If you're new to the autograder, start by using one of the built-in presets. This will help you get a feel for how the system works before you start creating your own custom assignments.
* **Clear and Concise Tests**: Write tests that are easy to understand and that test a single concept. This will make it easier for students to understand their mistakes.
* **Meaningful Feedback**: Provide feedback that is helpful and constructive. Avoid generic messages and try to explain *why* a student's code is incorrect.
* **Use Subjects to Group Tests**: Grouping tests into subjects makes it easier to manage your grading criteria and to provide students with a clear overview of their performance.
