# Grading operations

The [ordered grading flow](../core/pipeline-architecture.md) is implemented in one
coordinator with explicit intermediate values. These pages describe its domain
operations; they are not configurable step classes or a second pipeline API.

- [Resolve templates during compilation](01-load-template.md)
- [Compile the criteria tree](02-build-tree.md)
- [Acquire and close execution resources](03-sandbox.md)
- [Prepare fixtures, commands and servers](04-pre-flight.md)
- [Batch AI assessments](04.5-ai-batch.md)
- [Assess criteria and calculate the grade](05-grade.md)
- [Find feedback focus](06-focus.md)
- [Render requested feedback](07-feedback.md)
- [Publish the finalized outcome in the host](08-export.md)

Compilation is offline. Runtime resources are selected from the submitted
language, selected evaluators and preparation. Required failures stop grading;
optional feedback failures preserve the grade. Resources close before the host
receives the finalized outcome. Diagnostics never supply data to later operations.
