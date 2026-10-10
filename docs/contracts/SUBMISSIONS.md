# Accepted submission input

HTTP and GitHub Actions accept nonempty collections of UTF-8 source text. An
individual file may be empty. There is no binary upload or base64 source format:
no supported assignment requires it, and wrapping text would add a second
representation without preserving anything that UTF-8 cannot preserve already.
NUL-containing files, invalid UTF-8 and unpaired Unicode surrogates are rejected.
Content is never trimmed, newline-normalized or Unicode-normalized. A UTF-8 BOM,
CRLF, trailing newlines and non-ASCII source survive transport and storage.

## Paths and limits

Use canonical relative POSIX paths such as `src/main.py`. Names are case-sensitive
and must already be Unicode NFC. The hosts reject absolute and drive-qualified
paths, backslashes, control characters, empty names, `.`/`..` components, repeated
separators, trailing separators, duplicates and file/directory collisions. They
do not resolve aliases or rename files. Actions also rejects symlinks and special
files, and fails when a directory or file cannot be read. It excludes `.git`,
`.github` and `.autograder` directories from collection. Sandbox path checks
remain a second boundary for trusted Python callers and filesystem operations.

Both hosts use these conservative limits from `submission_contract.py`:

| Input | Inclusive limit |
| --- | --- |
| Files | 100 |
| Filename | 255 UTF-8 bytes |
| One source file | 1 MiB of UTF-8 |
| All source files | 5 MiB of UTF-8 |
| One metadata object, including top-level audit metadata | 16 KiB |
| All file metadata plus top-level audit metadata | 64 KiB |
| HTTP request body | 32 MiB of received bytes |

Metadata size uses compact JSON with `ensure_ascii=False`, no spaces and finite
numbers only. Source sizes count encoded content, not JSON escaping. The request
limit also counts names, metadata, framing and escaping; it is enforced on the
actual ASGI stream, even without `Content-Length`, before JSON parsing and
acceptance. Compressed bodies are unsupported (415); JSON bodies must be UTF-8.
The deliberate execution endpoint retains its smaller source and case limits.
External result ingestion also bounds its audit metadata and HTTP body, but does
not require source files: it attests an already finalized outcome.

HTTP schema violations return 422 with `detail: [{path, code, message}]` and no
echoed source. Oversized HTTP bodies return 413 with code `REQUEST_TOO_LARGE` in
the same envelope. No rejected input creates a submission or dispatches grading.
Actions fails collection before evaluation and logs a clear input error. Limits
are initial safety budgets, not a claim about sustainable grading capacity.

## Scope, changed lines and metadata

An omitted `evaluation_scope` permits all eligible files to be assessment targets.
A supplied `scoped_files` must be a nonempty, duplicate-free subset of submitted
canonical filenames. Eligibility and explicit criterion targets follow the
[evaluator selection contract](FILES.md). Scope does not remove context needed
to execute the program and is not a universal execution or privacy boundary.
AI/provider context follows the selected evaluator's explicit context policy.

`changed_lines` is either null/absent, or a list of unique integer line numbers
from 1 through the number of existing text lines (`str.splitlines()` semantics;
a trailing line terminator does not add a phantom line). Booleans, numeric
strings, duplicates, nonpositive and out-of-range values are rejected. An empty
file can only have absent/null or empty changed lines. Absence means no change
information was supplied; `[]` means explicitly no changed lines. The generic
grader does not infer changed-line-only assessment from either value.

Per-file `file_metadata` is opaque evaluator context, exposed as
`SubmissionFile.metadata` to the selected evaluator. Top-level `metadata` is host
audit data and is stored as `submission_metadata`; the grader never interprets
it. Locale and evaluation scope are separate persisted execution inputs.

For example, submit both Python source files and a README as context:

```json
{
  "external_assignment_id": "python-exercise",
  "external_user_id": "student-42",
  "username": "Student",
  "locale": "pt-br",
  "files": [
    {"filename": "src/main.py", "content": "import helper\r\n", "changed_lines": [],
     "file_metadata": {"review_reference": "opaque"}},
    {"filename": "src/helper.py", "content": "value = 1\n"},
    {"filename": "README.md", "content": "Exercise notes\n"}
  ],
  "evaluation_scope": {"scoped_files": ["src/main.py"]},
  "metadata": {"client_reference": "opaque-audit-reference"}
}
```

The static Python evaluator assesses `src/main.py`; the helper remains available
for execution and the README does not require an AST. Whole-submission checks
retain their documented file input. No metadata key changes file selection.

## Source, fixtures and generated artifacts

Submitted files are source/context under the execution workspace's source root.
Trusted definition preparation supplies fixtures via logical `reference` values
resolved by the host and relative fixture-root `path` values. A fixture reference
is never an arbitrary submitted filename or a path to open on the web server.
Generated artifacts are outputs read through the execution session after the
program runs; they are not extra submitted source or an implicit upload channel.
See [host capabilities](CAPABILITIES.md) for ownership and workspace mapping.

## Details and migration

Compact polling and history omit files, metadata, scope and the result tree.
Authenticated `GET /api/v1/submissions/{id}/details` returns each stored file as
an object under its filename key:

```json
{
  "submission_files": {
    "src/main.py": {
      "filename": "src/main.py",
      "content": "import helper\r\n",
      "changed_lines": [],
      "file_metadata": {"review_reference": "opaque"}
    }
  },
  "locale": "pt-br",
  "evaluation_scope": {"scoped_files": ["src/main.py"]},
  "submission_metadata": {"client_reference": "opaque-audit-reference"}
}
```

Clients previously reading `details.submission_files[name]` as a string must now
read `.content`. Legacy string-valued stored files project as objects with null
metadata and changed lines; they are not revalidated or assigned invented change
information. Old history retains its unverified provenance status.

Before upgrading clients, send canonical names, remove empty scopes, and omit
changed-line data when unavailable rather than sending stale or deleted-file line
numbers. Put binary fixtures in trusted host fixture storage; restrict the Action
submission root to the intended text inputs. HTTP acceptance now returns 202
with a `Location` status URL after commit; clients should poll it to completion.
See [durable jobs](JOBS.md) for restart, attempt and delivery behavior.
