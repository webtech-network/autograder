# 3. System Architecture

This document provides a technical overview of the WebTech Autograder's architecture. The system is designed using the **Hexagonal Architecture** (also known as the **Ports and Adapters** pattern), which emphasizes a clear separation between the core application logic and the external services it interacts with.

## The Hexagonal Architecture

The primary goal of this architecture is to isolate the core business logic from the outside world. This is achieved by defining "ports" (interfaces) that the core application uses to communicate with external services, and "adapters" that implement these interfaces.

This approach offers several key benefits:

* **Technology Agnostic**: The core application is not tied to any specific technology or framework, making it easier to adapt to new technologies in the future.

* **Testability**: The core logic can be tested in isolation, without the need for external services or databases.

* **Maintainability**: The clear separation of concerns makes the codebase easier to understand, maintain, and extend.

## Core Subsystem (`/autograder/core`)

The heart of the autograder is the **core subsystem**, located in the `/autograder/core` directory. This is where all the business logic for grading assignments resides. The core is completely self-contained and has no knowledge of the outside world.

### The `autograder_facade.py`

The `autograder_facade.py` acts as the single entry point to the core subsystem. It exposes a simple, high-level API that the adapters use to interact with the core logic. This facade is responsible for orchestrating the entire grading process, from parsing the configuration files to generating the final feedback report.

### `AutograderRequest` and `AutograderResponse`

The core subsystem communicates with the outside world through two simple data structures:

* **`AutograderRequest`**: This object encapsulates all the data that the core needs to perform a grading session, including the student's submission files, the test files, and the grading criteria.

* **`AutograderResponse`**: This object contains the results of the grading session, including the final score and the feedback report.

## Ports and Adapters (`/connectors`)

The `/connectors` directory contains the **ports** and **adapters** that allow the core subsystem to communicate with the outside world.

### Ports

A **port** is simply an interface that defines a set of operations that the core application can perform. For example, there might be a port for fetching a student's submission, or a port for sending a feedback report.

### Adapters

An **adapter** is a concrete implementation of a port. It's responsible for translating the core application's requests into the specific format required by an external service, and for translating the service's responses back into a format that the core can understand.

The autograder currently has two adapters:

* **GitHub Actions Adapter**: This adapter allows the autograder to be run as a GitHub Action. It's responsible for fetching the student's submission from the GitHub repository, running the grading process, and posting the feedback as a comment on the commit.

* **API Adapter**: This adapter exposes a simple REST API that can be used to submit assignments for grading. It's responsible for handling the HTTP requests and responses, and for passing the submission data to the core subsystem.

## Architectural Diagrams

### High-Level Architecture

This diagram provides a high-level overview of the Hexagonal Architecture.

![High-Level Architecture](/docs/imgs/hexagonal_architecture.png)

### Grading Process Sequence

This sequence diagram illustrates the flow of a grading request from an adapter to the core and back.

![Grading Process Sequence](/docs/imgs/grading_sequence.png)
