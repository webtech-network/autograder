# Calculate the grade

`grade(criteria_tree, results)` (`autograder/services/grading.py`) combines the
ID-keyed results produced by [assessment](04.5-ai-batch.md) with the compiled
tree's effective weights and builds the frozen canonical `ResultOutcomeTree`
once. It executes no evaluator and receives no session, provider or AI-specific
value; a missing criterion result is a required `MISSING_EVALUATOR_RESULT`
failure. Weights, traversal and score arithmetic come from
`autograder/models/contracts/scoring.py`.

The coordinator then applies `verify_outcome_tree(criteria, tree)`, the same
structural check the HTTP host applies to externally attested outcomes, before
optional reporting. Required evaluator errors
and invalid results fail the entire grade with null score/tree. Student
compilation/runtime/timeout responses during assessment can be valid zero scores.

There is no grade wrapper or journal lookup. See
[grading semantics](../features/grading_engine.md) and
[outcome invariants](../contracts/OUTCOMES.md).
