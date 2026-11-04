# Calculate the grade

`GraderService.grade_from_tree(criteria_tree, results)` combines the ID-keyed
results produced by [assessment](04.5-ai-batch.md) with the compiled tree's
weights and returns a `ResultTree`. It executes no evaluator and receives no
session, provider or AI-specific value; a missing criterion result is a
required `MISSING_EVALUATOR_RESULT` failure.

The coordinator calculates the final score and validates a frozen
`ResultOutcomeTree` snapshot before optional reporting. Required evaluator errors
and invalid results fail the entire grade with null score/tree. Student
compilation/runtime/timeout responses during assessment can be valid zero scores.

There is no grade wrapper or journal lookup. See
[grading semantics](../features/grading_engine.md) and
[outcome invariants](../contracts/OUTCOMES.md).
