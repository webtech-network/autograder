# Assess criteria and calculate the grade

`GraderService.grade_from_tree` receives the compiled criteria tree, submission
files and language, optional session, AI assessments, locale and evaluation scope
as ordinary arguments. Its per-run grader resolves inputs, invokes evaluators,
and returns a `ResultTree`. Static structural parsing is lazy within that traversal.

The coordinator calculates the final score and validates a frozen
`ResultOutcomeTree` snapshot before optional reporting. Required evaluator errors
and invalid results fail the entire grade with null score/tree. Student
compilation/runtime/timeout responses during assessment can be valid zero scores.

There is no grade wrapper or journal lookup. See
[grading semantics](../features/grading_engine.md) and
[outcome invariants](../contracts/OUTCOMES.md).
