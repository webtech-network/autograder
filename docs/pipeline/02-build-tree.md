# Criteria tree compilation

`compile_definition` validates the v1 definition, normalizes evaluator parameters
exactly once, and calls `build_criteria_tree` with those canonical values. Tree
construction never validates or normalizes parameters again. The resulting
immutable `CriteriaTree` holds base, optional bonus/penalty, nested subjects and
tests. Each test embeds the evaluator, stable criterion ID, display name, deeply
frozen normalized parameters, relative weight and optional file target. Grading
gives each evaluator invocation and each reported result its own mutable copy.

Sibling weights are ratios; all-zero siblings share equal weight. Mixed groups
use the explicit `subjects_weight` split. Base weight is 100; bonus and penalty
weights are caps. See [criteria trees](../core/criteria-tree.md).

The coordinator passes this already-built tree directly to AI batching and
grading. There is no runtime tree-building or attachment wrapper.
Invalid definitions fail compilation before any execution resource is opened.
