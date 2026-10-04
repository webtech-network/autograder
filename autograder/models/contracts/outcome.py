"""Versioned terminal grading data shared by every hosting adapter.

Pipeline diagnostics and publication state deliberately do not belong here.
"""
from datetime import datetime, timezone
import re
from math import isclose
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter, field_validator, model_validator

from autograder.models.contracts.provenance import DefinitionProvenance

Score = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False, strict=True)]
Weight = Annotated[float, Field(ge=0, allow_inf_nan=False, strict=True)]


class _FrozenDict(dict):
    """Keep nested JSON immutable while preserving ordinary JSON serialization."""
    def _immutable(self, *args, **kwargs):
        raise TypeError("Terminal outcome data is immutable")
    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = __ior__ = _immutable
    def __copy__(self):
        return self
    def __deepcopy__(self, memo):
        return self


class _FrozenList(list):
    def _immutable(self, *args, **kwargs):
        raise TypeError("Terminal outcome data is immutable")
    __setitem__ = __delitem__ = append = clear = extend = insert = pop = remove = reverse = sort = __iadd__ = __imul__ = _immutable
    def __copy__(self):
        return self
    def __deepcopy__(self, memo):
        return self


def _freeze(value):
    if isinstance(value, dict):
        return _FrozenDict({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return _FrozenList(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    return value


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False, revalidate_instances="always")

    @model_validator(mode="after")
    def freeze_json(self):
        for name in type(self).model_fields:
            value = getattr(self, name)
            if isinstance(value, dict):
                object.__setattr__(self, name, _freeze(value))
        return self


class OutcomeError(ContractModel):
    code: str = Field(min_length=1, pattern=r"^[A-Z][A-Z0-9_]*$")
    message: str = Field(min_length=1)
    category: Literal["definition", "submission", "capability", "provider", "internal"]
    retryable: bool = Field(strict=True)
    correlation_id: str = Field(min_length=1)


class TestOutcome(ContractModel):
    id: str = Field(min_length=1)
    evaluator: str = Field(min_length=1)
    type: Literal["test"] = "test"
    name: str
    score: Score
    weight: Weight
    report: str = ""
    file_target: tuple[str, ...] | None = None
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class SubjectOutcome(ContractModel):
    name: str
    type: Literal["subject"] = "subject"
    score: Score
    weight: Weight
    subjects: tuple["SubjectOutcome", ...] = ()
    tests: tuple[TestOutcome, ...] = ()
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_score(self):
        _validate_holder(self)
        return self


class CategoryOutcome(ContractModel):
    name: Literal["base", "bonus", "penalty"]
    type: Literal["category"] = "category"
    score: Score
    weight: Annotated[float, Field(ge=0, le=100, strict=True, allow_inf_nan=False)]
    subjects: tuple[SubjectOutcome, ...] = ()
    tests: tuple[TestOutcome, ...] = ()
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_score(self):
        _validate_holder(self)
        return self


def _validate_holder(holder):
    children = (*holder.subjects, *holder.tests)
    if not children or sum(child.weight for child in children) <= 0:
        raise ValueError("Result holders require positively weighted children")
    score = sum(child.score * child.weight for child in children) / sum(child.weight for child in children)
    if not isclose(holder.score, score, abs_tol=0.011):
        raise ValueError("Holder score is inconsistent with child scores and weights")


class ResultOutcomeTree(ContractModel):
    name: Literal["root"] = "root"
    type: Literal["root"] = "root"
    score: Score
    base: CategoryOutcome
    bonus: CategoryOutcome | None = None
    penalty: CategoryOutcome | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_tree(self):
        for name in ("base", "bonus", "penalty"):
            node = getattr(self, name)
            if node is not None and node.name != name:
                raise ValueError("Category names must match their tree position")
        if self.base.weight != 100:
            raise ValueError("Base category weight must be 100")
        score = self.base.score
        if self.bonus:
            score += self.bonus.score / 100 * self.bonus.weight
        if self.penalty:
            score -= (100 - self.penalty.score) / 100 * self.penalty.weight
        if not isclose(self.score, min(100, max(0, score)), abs_tol=0.021):
            raise ValueError("Root score is inconsistent with category scores")
        ids = [test.id for test in iter_outcome_tests(self)]
        if len(ids) != len(set(ids)):
            raise ValueError("Criterion IDs must be unique within a result tree")
        return self


def iter_outcome_tests(tree: ResultOutcomeTree):
    def walk(holder):
        yield from holder.tests
        for subject in holder.subjects:
            yield from walk(subject)
    for category in (tree.base, tree.bonus, tree.penalty):
        if category:
            yield from walk(category)


def outcome_score_vector(outcome: "CompletedOutcome") -> dict[str, float]:
    return {test.id: test.score for test in iter_outcome_tests(outcome.tree)}


class FeedbackOutcome(ContractModel):
    status: Literal["disabled", "completed", "failed"] = "disabled"
    content: str | None = None
    error: OutcomeError | None = None

    @model_validator(mode="after")
    def validate_status(self):
        _validate_enrichment(self)
        return self


class ComparisonContent(ContractModel):
    score_delta: Annotated[float, Field(ge=-100, le=100, allow_inf_nan=False, strict=True)]
    improved: bool = Field(strict=True)
    test_deltas: tuple["CriterionDelta", ...] = ()

    @model_validator(mode="after")
    def validate_comparison(self):
        if self.improved != (self.score_delta > 0):
            raise ValueError("Comparison direction is inconsistent with its score delta")
        ids = [item.path for item in self.test_deltas]
        if len(set(ids)) != len(ids):
            raise ValueError("Comparison criterion IDs must be unique")
        return self


class CriterionDelta(ContractModel):
    path: str = Field(min_length=1, description="Criterion ID, independent of display names")
    status: Literal["improved", "regressed", "unchanged", "introduced", "removed"]
    baseline_score: Score | None = None
    head_score: Score | None = None
    delta: Annotated[float, Field(ge=-100, le=100, allow_inf_nan=False, strict=True)] | None = None

    @model_validator(mode="after")
    def validate_delta(self):
        if self.status == "introduced":
            if self.baseline_score is not None or self.head_score is None or self.delta is not None:
                raise ValueError("Introduced criteria require only a head score")
        elif self.status == "removed":
            if self.baseline_score is None or self.head_score is not None or self.delta is not None:
                raise ValueError("Removed criteria require only a baseline score")
        else:
            if self.baseline_score is None or self.head_score is None or self.delta is None:
                raise ValueError("Compared criteria require two scores and a delta")
            expected = self.head_score - self.baseline_score
            direction = "improved" if expected > 0 else "regressed" if expected < 0 else "unchanged"
            if direction != self.status or not isclose(self.delta, expected, abs_tol=0.011):
                raise ValueError("Criterion comparison is inconsistent with its scores")
        return self


class ComparisonOutcome(ContractModel):
    status: Literal["disabled", "completed", "failed"] = "disabled"
    content: ComparisonContent | None = None
    error: OutcomeError | None = None

    @model_validator(mode="after")
    def validate_status(self):
        _validate_enrichment(self)
        return self


def _validate_enrichment(enrichment):
    if enrichment.status == "completed":
        if enrichment.content is None or enrichment.error is not None:
            raise ValueError("Completed enrichment requires content and no error")
    elif enrichment.status == "failed":
        if enrichment.content is not None or enrichment.error is None:
            raise ValueError("Failed enrichment requires an error and no content")
    elif enrichment.content is not None or enrichment.error is not None:
        raise ValueError("Disabled enrichment must omit content and error")


class OutcomeBase(ContractModel):
    schema_version: Literal["1.0"]
    execution_id: str = Field(min_length=1)
    language: Literal["python", "java", "c", "cpp", "node"] | None = None
    provenance: DefinitionProvenance
    started_at: datetime
    finished_at: datetime
    duration_ms: int = Field(ge=0, strict=True)
    feedback: FeedbackOutcome = Field(default_factory=FeedbackOutcome)
    comparison: ComparisonOutcome = Field(default_factory=ComparisonOutcome)

    @field_validator("started_at", "finished_at", mode="before")
    @classmethod
    def validate_timestamp_encoding(cls, value):
        # Python hosts may supply aware datetime objects; the wire contract is
        # RFC3339 text, never a Unix epoch number or a numeric string.
        if isinstance(value, datetime):
            return value
        if not isinstance(value, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})", value
        ):
            raise ValueError("Outcome timestamps require RFC3339 strings with offsets")
        return value

    @model_validator(mode="after")
    def validate_times(self):
        for name in ("started_at", "finished_at"):
            value = getattr(self, name)
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("Outcome timestamps require UTC offsets")
            object.__setattr__(self, name, value.astimezone(timezone.utc))
        if self.finished_at < self.started_at:
            raise ValueError("Outcome finish precedes start")
        if self.feedback.error and self.feedback.error.correlation_id != self.execution_id:
            raise ValueError("Feedback error correlation must identify the execution")
        if self.comparison.error and self.comparison.error.correlation_id != self.execution_id:
            raise ValueError("Comparison error correlation must identify the execution")
        return self


class CompletedOutcome(OutcomeBase):
    status: Literal["completed"]
    score: Score
    tree: ResultOutcomeTree
    error: None = None

    @model_validator(mode="after")
    def validate_grade(self):
        if not isclose(self.score, self.tree.score, abs_tol=0.011):
            raise ValueError("Outcome score does not match the result tree")
        return self


class FailedOutcome(OutcomeBase):
    status: Literal["failed"]
    score: None = None
    tree: None = None
    error: OutcomeError

    @model_validator(mode="after")
    def validate_failure(self):
        if self.error.correlation_id != self.execution_id:
            raise ValueError("Error correlation must identify the execution")
        if self.feedback.status == "completed" or self.comparison.status == "completed":
            raise ValueError("Failed grading cannot carry completed enrichment")
        return self


TerminalOutcome = Annotated[CompletedOutcome | FailedOutcome, Field(discriminator="status")]
_outcome_adapter = TypeAdapter(TerminalOutcome)


def validate_outcome(data: Any) -> CompletedOutcome | FailedOutcome:
    return _outcome_adapter.validate_python(data)


def outcome_json_schema() -> dict[str, Any]:
    schema = _outcome_adapter.json_schema()
    schema["$id"] = "https://webtech.network/autograder/contracts/outcome/1.0"
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    return schema
