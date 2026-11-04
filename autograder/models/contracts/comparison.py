"""Pure, on-demand comparison of two canonical terminal outcomes.

A comparison is never part of grading. It reads two completed outcomes and the
exact normalized definitions they are bound to, joins criteria strictly by
criterion ID, and never regrades, stores, or mutates either outcome. Score
vectors are always derived from the authoritative trees; callers cannot supply
an independent tree or vector.

Compatibility rules (see docs/contracts/OUTCOMES.md, "Baseline comparison"):

* Same definition hash: ``same_definition``. Overall and per-criterion deltas.
* Different hash: ``cross_revision``. The overall score is not comparable as a
  whole (``score_delta`` is null). Per criterion, matched by ID only:
  identical evaluator type, normalized parameters, file target and effective
  weight/category -> improved/regressed/unchanged; identical semantics but a
  changed effective weight or category -> ``reweighted`` with its score delta;
  changed type/parameters/target -> ``redefined`` with no delta; head-only ->
  ``introduced``; baseline-only -> ``removed``.
"""
from dataclasses import dataclass
from math import isclose
from typing import Annotated, Any, Literal, Mapping

from pydantic import Field, ValidationError, model_validator

from autograder.models.contracts.definition import CompiledDefinition, GradingDefinition, definition_hash
from autograder.models.contracts.outcome import (
    CompletedOutcome, ContractModel, FailedOutcome, Score, validate_outcome,
)
from autograder.models.contracts.provenance import DefinitionProvenance
from autograder.models.contracts.scoring import iter_tests, normalized_sibling_weights

Delta = Annotated[float, Field(ge=-100, le=100, allow_inf_nan=False, strict=True)]
Category = Literal["base", "bonus", "penalty"]
CriterionStatus = Literal["improved", "regressed", "unchanged", "reweighted", "redefined", "introduced", "removed"]

SAME_DEFINITION_EXPLANATION = (
    "Both outcomes are bound to the same normalized definition; overall and per-criterion "
    "score deltas are directly comparable."
)
CROSS_REVISION_EXPLANATION = (
    "The outcomes are bound to different definition revisions, so the overall score is not "
    "comparable as a whole and score_delta is null. Criteria are matched only by criterion ID: "
    "reweighted criteria changed effective weight or category, redefined criteria changed "
    "evaluator type, normalized parameters or file target and carry no delta."
)
DEFINITION_SECTIONS = ("schema_version", "templates", "languages", "criteria", "preparation", "feedback", "metadata")


class ComparisonError(ValueError):
    """A requested comparison cannot be computed; ``code`` is a stable machine code."""

    def __init__(self, code: str, message: str, *, side: str | None = None):
        self.code = code
        self.message = message
        self.side = side
        super().__init__(message)


class ComparedOutcome(ContractModel):
    """Identity and grade of one compared outcome."""
    execution_id: str = Field(min_length=1)
    score: Score
    provenance: DefinitionProvenance


class CriterionComparison(ContractModel):
    """One criterion joined by ID; absent sides carry no label, score, category or weight."""
    criterion_id: str = Field(min_length=1, description="Stable criterion ID; display labels never identify criteria")
    status: CriterionStatus
    baseline_label: str | None = None
    head_label: str | None = None
    baseline_score: Score | None = None
    head_score: Score | None = None
    delta: Delta | None = Field(None, description="head_score - baseline_score; null when not comparable")
    baseline_category: Category | None = None
    head_category: Category | None = None
    baseline_weight: float | None = Field(
        None, ge=0, allow_inf_nan=False,
        description="Effective final-score points: category weight times normalized share within it")
    head_weight: float | None = Field(None, ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_status(self):  # pylint: disable=too-many-branches
        """Each status has exactly one valid shape."""
        baseline = (self.baseline_label, self.baseline_score, self.baseline_category, self.baseline_weight)
        head = (self.head_label, self.head_score, self.head_category, self.head_weight)
        has_baseline = all(value is not None for value in baseline)
        has_head = all(value is not None for value in head)
        if any(value is not None for value in baseline) and not has_baseline:
            raise ValueError("Baseline criterion data must be complete or absent")
        if any(value is not None for value in head) and not has_head:
            raise ValueError("Head criterion data must be complete or absent")
        if self.status == "introduced":
            if has_baseline or not has_head or self.delta is not None:
                raise ValueError("Introduced criteria carry only head data")
        elif self.status == "removed":
            if not has_baseline or has_head or self.delta is not None:
                raise ValueError("Removed criteria carry only baseline data")
        elif self.status == "redefined":
            if not (has_baseline and has_head) or self.delta is not None:
                raise ValueError("Redefined criteria carry both sides and no delta")
        else:
            if not (has_baseline and has_head) or self.delta is None:
                raise ValueError("Compared criteria require both sides and a delta")
            if not isclose(self.delta, self.head_score - self.baseline_score, abs_tol=0.011):
                raise ValueError("Criterion delta is inconsistent with its scores")
            if self.status != "reweighted":
                direction = "improved" if self.delta > 0 else "regressed" if self.delta < 0 else "unchanged"
                if direction != self.status:
                    raise ValueError("Criterion status is inconsistent with its delta")
        return self


class OutcomeComparison(ContractModel):
    """On-demand comparison of two completed outcomes; never part of a grading outcome."""
    compatibility: Literal["same_definition", "cross_revision"]
    baseline: ComparedOutcome
    head: ComparedOutcome
    score_delta: Delta | None = Field(None, description="Overall head - baseline; null across revisions")
    improved: bool | None = Field(None, strict=True)
    explanation: str = Field(min_length=1)
    changed_definition_sections: tuple[str, ...] = ()
    criteria: tuple[CriterionComparison, ...] = ()

    @model_validator(mode="after")
    def validate_compatibility(self):
        """Overall deltas exist only for one definition hash."""
        same_hash = self.baseline.provenance.definition_hash == self.head.provenance.definition_hash
        if self.compatibility == "same_definition":
            if not same_hash or self.changed_definition_sections:
                raise ValueError("Same-definition comparisons require one definition hash")
            if self.score_delta is None or self.improved != (self.score_delta > 0):
                raise ValueError("Same-definition comparisons require a consistent overall delta")
            if not isclose(self.score_delta, self.head.score - self.baseline.score, abs_tol=0.011):
                raise ValueError("Overall delta is inconsistent with outcome scores")
            if any(item.status in ("reweighted", "redefined", "introduced", "removed") for item in self.criteria):
                raise ValueError("Same-definition comparisons cannot change criteria")
        else:
            if same_hash:
                raise ValueError("Cross-revision comparisons require different definition hashes")
            if self.score_delta is not None or self.improved is not None:
                raise ValueError("Cross-revision comparisons have no overall delta")
        ids = [item.criterion_id for item in self.criteria]
        if len(ids) != len(set(ids)):
            raise ValueError("Comparison criterion IDs must be unique")
        return self


@dataclass(frozen=True)
class _Criterion:
    label: str
    score: float
    evaluator: str
    parameters: Any
    file: str | None
    category: str
    weight: float


@dataclass(frozen=True)
class _Bound:
    outcome: CompletedOutcome
    definition: GradingDefinition
    criteria: dict[str, _Criterion]
    order: tuple[str, ...]


def _definition_criteria(definition: GradingDefinition):
    """Yield (test, category, effective final-score points) using the engine's weight rules."""
    def walk(group, share):
        tests, subjects = group.tests or [], group.subjects or []
        if tests and subjects:
            split = group.subjects_weight
            test_weights = normalized_sibling_weights([test.weight for test in tests], (100.0 - split) / 100.0)
            subject_weights = normalized_sibling_weights([subject.weight for subject in subjects], split / 100.0)
        else:
            test_weights = normalized_sibling_weights([test.weight for test in tests])
            subject_weights = normalized_sibling_weights([subject.weight for subject in subjects])
        for test, weight in zip(tests, test_weights):
            yield test, share * weight / 100.0
        for subject, weight in zip(subjects, subject_weights):
            yield from walk(subject, share * weight / 100.0)

    for name in ("base", "bonus", "penalty"):
        category = getattr(definition.criteria, name)
        if category is not None:
            for test, share in walk(category, 1.0):
                yield test, name, category.weight * share


def _definition(side, value) -> GradingDefinition:
    if isinstance(value, CompiledDefinition):
        value = value.definition
    if isinstance(value, GradingDefinition):
        value = value.model_dump(mode="json")
    try:
        return GradingDefinition.model_validate(value)
    except ValidationError as exc:
        raise ComparisonError("INVALID_DEFINITION", f"The {side} definition is not a valid grading definition",
                              side=side) from exc


def _outcome(side, value):
    try:
        if isinstance(value, (CompletedOutcome, FailedOutcome)):
            value = value.model_dump(mode="json")
        return validate_outcome(value)
    except ValidationError as exc:
        raise ComparisonError("INVALID_OUTCOME", f"The {side} outcome is not a valid terminal outcome",
                              side=side) from exc


def _bind(side, outcome_value, definition_value) -> _Bound:
    outcome = _outcome(side, outcome_value)
    if outcome.status != "completed":
        raise ComparisonError("OUTCOME_NOT_COMPLETED",
                              f"The {side} outcome failed and has no authoritative grade", side=side)
    definition = _definition(side, definition_value)
    if definition_hash(definition) != outcome.provenance.definition_hash:
        raise ComparisonError("DEFINITION_MISMATCH",
                              f"The {side} definition is not the normalized definition bound to its outcome",
                              side=side)
    declared = {test.id: (test, category, weight) for test, category, weight in _definition_criteria(definition)}
    results = [test for _, test in iter_tests(outcome.tree)]
    if {result.id for result in results} != set(declared) or any(
            result.evaluator != declared[result.id][0].type for result in results):
        raise ComparisonError("DEFINITION_MISMATCH",
                              f"The {side} result tree does not match its bound definition", side=side)
    criteria = {}
    for result in results:
        test, category, weight = declared[result.id]
        criteria[result.id] = _Criterion(label=result.name, score=result.score, evaluator=test.type,
                                         parameters=test.parameters, file=test.file,
                                         category=category, weight=weight)
    return _Bound(outcome, definition, criteria, tuple(result.id for result in results))


def _side(prefix, criterion: _Criterion | None) -> dict:
    if criterion is None:
        return {}
    return {f"{prefix}_label": criterion.label, f"{prefix}_score": criterion.score,
            f"{prefix}_category": criterion.category, f"{prefix}_weight": round(criterion.weight, 6)}


def _row(criterion_id, before: _Criterion | None, after: _Criterion | None, same_definition: bool):
    values = {"criterion_id": criterion_id, **_side("baseline", before), **_side("head", after)}
    if before is None:
        return CriterionComparison(status="introduced", **values)
    if after is None:
        return CriterionComparison(status="removed", **values)
    delta = round(after.score - before.score, 2)
    if not same_definition:
        if (before.evaluator, before.parameters, before.file) != (after.evaluator, after.parameters, after.file):
            return CriterionComparison(status="redefined", **values)
        if before.category != after.category or not isclose(before.weight, after.weight, rel_tol=1e-9, abs_tol=1e-9):
            return CriterionComparison(status="reweighted", delta=delta, **values)
    status = "improved" if delta > 0 else "regressed" if delta < 0 else "unchanged"
    return CriterionComparison(status=status, delta=delta, **values)


def compare_outcomes(baseline_outcome: CompletedOutcome | FailedOutcome | Mapping[str, Any],
                     head_outcome: CompletedOutcome | FailedOutcome | Mapping[str, Any],
                     baseline_definition: GradingDefinition | CompiledDefinition | Mapping[str, Any],
                     head_definition: GradingDefinition | CompiledDefinition | Mapping[str, Any]) -> OutcomeComparison:
    """Compare two completed canonical outcomes bound to their exact normalized definitions.

    Pure: no grading, persistence, provider, or registry access. Each definition
    must hash to its outcome's ``provenance.definition_hash`` (pass
    ``compile_definition(...).definition`` or the stored snapshot). Raises
    ``ComparisonError`` with a stable code when the inputs cannot be compared.
    """
    baseline = _bind("baseline", baseline_outcome, baseline_definition)
    head = _bind("head", head_outcome, head_definition)
    same = baseline.outcome.provenance.definition_hash == head.outcome.provenance.definition_hash
    order = list(head.order) + [identity for identity in baseline.order if identity not in head.criteria]
    rows = tuple(_row(identity, baseline.criteria.get(identity), head.criteria.get(identity), same)
                 for identity in order)
    if same:
        score_delta = round(head.outcome.score - baseline.outcome.score, 2)
        overall = {"score_delta": score_delta, "improved": score_delta > 0, "explanation": SAME_DEFINITION_EXPLANATION}
        changed = ()
    else:
        before, after = baseline.definition.model_dump(mode="json"), head.definition.model_dump(mode="json")
        overall = {"score_delta": None, "improved": None, "explanation": CROSS_REVISION_EXPLANATION}
        changed = tuple(section for section in DEFINITION_SECTIONS if before.get(section) != after.get(section))

    def compared(bound):
        return ComparedOutcome(execution_id=bound.outcome.execution_id, score=bound.outcome.score,
                               provenance=bound.outcome.provenance)

    return OutcomeComparison(compatibility="same_definition" if same else "cross_revision",
                             baseline=compared(baseline), head=compared(head),
                             changed_definition_sections=changed, criteria=rows, **overall)
