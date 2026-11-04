"""Bind stored locales and outcome error codes to the closed core vocabularies (COR-07).

* ``submissions.locale``: supported values are stored in canonical form
  (``pt_BR`` -> ``pt-br``). Any other value was rendered in English by the old
  translator fallback, so it is stored as ``en``, which is what it received.
* ``submission_results.outcome``: the HTTP host's former unexpected-failure code
  ``EXECUTION_FAILED`` becomes the single code ``EXECUTION_ERROR``. Any other
  unpublished code aborts the upgrade with the affected result IDs, because such
  a row could not be served under the closed outcome contract.

Downgrade keeps the data: the previous code accepts every value written here.
"""
from copy import deepcopy

from alembic import op
import sqlalchemy as sa

from autograder.models.contracts.outcome import OUTCOME_ERROR_CODES
from autograder.models.locale import DEFAULT_LOCALE, parse_locale

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None

_LEGACY_CODES = {"EXECUTION_FAILED": ("EXECUTION_ERROR", "The grading execution could not complete.")}


def _canonical_locale(value):
    try:
        return parse_locale(value).value
    except ValueError:
        return DEFAULT_LOCALE.value


def _rewrite_errors(outcome):
    """Return (outcome with legacy codes replaced, unpublished codes that remain)."""
    unknown = []
    rewritten = deepcopy(outcome)
    for owner in (rewritten, rewritten.get("feedback"), rewritten.get("comparison")):
        error = owner.get("error") if isinstance(owner, dict) else None
        if not isinstance(error, dict):
            continue
        if error.get("code") in _LEGACY_CODES:
            code, message = _LEGACY_CODES[error["code"]]
            owner["error"] = {**error, "code": code, "message": message}
        elif error.get("code") not in OUTCOME_ERROR_CODES:
            unknown.append(error.get("code"))
    return rewritten, unknown


def upgrade():
    """Canonicalize stored locales and legacy codes; refuse unpublished codes."""
    connection = op.get_bind()
    submissions = sa.table("submissions", sa.column("locale", sa.String))
    for (stored,) in connection.execute(sa.select(submissions.c.locale).distinct()).all():
        canonical = _canonical_locale(stored)
        if canonical != stored:
            connection.execute(submissions.update().where(submissions.c.locale == stored)
                               .values(locale=canonical))

    results = sa.table("submission_results", sa.column("id", sa.Integer), sa.column("outcome", sa.JSON))
    unpublished = {}
    for row in connection.execute(sa.select(results.c.id, results.c.outcome)).all():
        if not isinstance(row.outcome, dict):  # SQL NULL or JSON null: no canonical outcome
            continue
        rewritten, unknown = _rewrite_errors(row.outcome)
        if unknown:
            unpublished[row.id] = unknown
        elif rewritten != row.outcome:
            connection.execute(results.update().where(results.c.id == row.id).values(outcome=rewritten))
    if unpublished:
        raise RuntimeError(
            "Stored outcomes use error codes outside the published vocabulary "
            f"(submission_results.id: codes): {unpublished}. Map each to a published code "
            "(docs/contracts/OUTCOMES.md) and run the upgrade again."
        )


def downgrade():
    """Nothing to undo: the previous release accepts every value written here."""
