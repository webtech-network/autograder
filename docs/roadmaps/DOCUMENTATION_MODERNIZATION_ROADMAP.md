# Documentation Modernization Roadmap

**Created:** March 12, 2026  
**Status:** In Progress  
**Purpose:** Bring all project documentation in sync with the actual codebase, fill gaps, and improve structure.

---

## Roadmap Items

### 🔴 Priority 1 — Critical Fixes (Documentation is Actively Wrong)

#### Item 1: Add Deliberate Code Execution (DCE) to API Documentation
- **Type:** New content for existing doc
- **File:** `docs/API.md`
- **Problem:** The DCE feature (`POST /api/v1/execute`) was added to the codebase but never added to the main API documentation. The endpoint, request/response schemas, and usage examples are entirely missing from `API.md`.
- **Action:** Add complete DCE endpoint documentation to `docs/API.md` including request body, response format, error handling, and examples.
- **Status:** ✅ Done

#### Item 2: Fix Incorrect Endpoint Paths in API Documentation
- **Type:** Fix existing doc
- **File:** `docs/API.md`
- **Problem:** The API doc references `POST /api/v1/grading-configs` and `GET /api/v1/grading-configs/{assignment_id}`, but the actual routes are `POST /api/v1/configs` and `GET /api/v1/configs/{external_assignment_id}`. The doc also uses `assignment_id` (integer) while the code uses `external_assignment_id` (string).
- **Action:** Correct all endpoint paths and field names to match the actual code.
- **Status:** ✅ Done

#### Item 3: Fix Incorrect Submission Schema in API Documentation
- **Type:** Fix existing doc
- **File:** `docs/API.md`
- **Problem:** The submission creation example uses `assignment_id`, `user_id`, and `language` (singular), but the actual schema uses `external_assignment_id`, `external_user_id`, and the language field is optional. The response schema also differs from actual `SubmissionResponse`.
- **Action:** Update the submission endpoint documentation to match `SubmissionCreate` and `SubmissionResponse` schemas.
- **Status:** ✅ Done

#### Item 4: Remove Fictional API Features from Documentation
- **Type:** Fix existing doc
- **File:** `docs/API.md`
- **Problem:** The API doc describes features that don't exist in the codebase:
  - Bearer token authentication (no auth middleware exists)
  - Rate limiting with `X-RateLimit-*` headers (no rate limiting middleware)
  - Webhooks endpoint (`POST /api/v1/webhooks`) (no webhook router exists)
  - Error response format with `error_code` and `timestamp` fields (actual errors use FastAPI's default `detail` format)
- **Action:** Remove fictional sections entirely or mark them as "Planned" if they're on the roadmap.
- **Status:** ✅ Done

#### Item 5: Add Missing Endpoints to API Documentation
- **Type:** New content for existing doc
- **File:** `docs/API.md`
- **Problem:** Several existing endpoints are undocumented:
  - `GET /api/v1/configs` (list all configurations)
  - `PUT /api/v1/configs/{config_id}` (update configuration)
  - `GET /api/v1/submissions/user/{external_user_id}` (list user submissions)
  - `GET /api/v1/templates` (list available templates)
  - `GET /api/v1/templates/{template_name}` (get template details)
  - `GET /api/v1/health` (health check)
  - `GET /api/v1/ready` (readiness check)
- **Action:** Document all endpoints with request/response examples.
- **Status:** ✅ Done

#### Item 6: Fix DCE Feature Documentation Schema Mismatch
- **Type:** Fix existing doc
- **Files:** `docs/deliberate_code_execution.md`, `docs/DCE_QUICK_START.md`
- **Problem:** The DCE documentation references `inputs` as the request field name, but the actual Pydantic schema uses `test_cases`. The response format shown is also outdated — the actual response wraps results in a `results` array (since DCE supports multiple test cases), but the docs show a flat single-result response.
- **Action:** Update field names and response format to match the actual `DeliberateCodeExecutionRequest` and `DeliberateCodeExecutionResponse` schemas.
- **Status:** ✅ Done

#### Item 7: Fix Core Structures Documentation
- **Type:** Fix existing doc
- **File:** `docs/core_structures.md`
- **Problem:** Multiple discrepancies with actual code:
  - `Submission` class shows `files: list[SubmissionFile]` but actual code uses `submission_files: Dict[str, SubmissionFile]`
  - Shows `metadata: dict` but actual has `language: Optional[Language]`
  - `GradingResult` shows `execution_metadata: dict` but actual has `focus: Optional[Focus]`, `error: Optional[str]`, `failed_at_step: Optional[str]` — no `execution_metadata` field
  - `TestResult` shows `passed: bool`, `execution_time: float`, `error: str` but actual has `subject_name: str`, `parameters: Optional[Dict]` — no `passed`/`execution_time`/`error` fields
  - `SubmissionFile` shows `path: str` but actual only has `filename` and `content`
- **Action:** Rewrite data structure documentation to match actual dataclass definitions.
- **Status:** ✅ Done

---

### 🟡 Priority 2 — Structural Improvements (Missing Documentation)

#### Item 8: Fix Broken Links in README and Other Docs
- **Type:** Fix existing docs
- **Files:** `README.md`, `docs/SETUP_CONFIG_QUICK_START.md`, `docs/pipeline_execution_tracking.md`
- **Problem:** Several links point to non-existent files:
  - `README.md` → `docs/templates/webdev.md` (doesn't exist)
  - `README.md` → `docs/NAMED_SETUP_COMMANDS.md` (doesn't exist)
  - `docs/pipeline_execution_tracking.md` → `docs/NAMED_SETUP_COMMANDS.md` (doesn't exist)
  - `docs/SETUP_CONFIG_QUICK_START.md` → `example_java_config_with_setup.json` (doesn't exist)
- **Action:** Updated all broken links:
  - `README.md`: `docs/templates/webdev.md` → `docs/templates/web_dev.md` (new file created)
  - `README.md`: `docs/NAMED_SETUP_COMMANDS.md` → `docs/index.md` (replaced with documentation index)
  - `docs/pipeline_execution_tracking.md`: Removed dead `NAMED_SETUP_COMMANDS.md` link
  - `docs/SETUP_CONFIG_QUICK_START.md`: `example_java_config_with_setup.json` → `configuration_examples.md`
- **Status:** ✅ Done

#### Item 9: Create Template Library Reference Documentation
- **Type:** New documentation
- **Files:** Created `docs/templates/` directory with per-template docs
- **Problem:** The README links to `docs/templates/webdev.md` which didn't exist. There was no reference documentation for any template's test functions, parameters, or usage.
- **Action:** Created three template reference docs:
  - `docs/templates/web_dev.md` — All 36 test functions across HTML (18), CSS (8), JavaScript (7), and project structure (3) categories with parameters, types, and usage examples
  - `docs/templates/input_output.md` — `expect_output` and `dont_fail` test functions with multi-language command resolution docs
  - `docs/templates/api_testing.md` — `health_check` and `check_response_json` test functions with HTTP-based testing explanation
- **Status:** ✅ Done

#### Item 10: Create Sandbox Manager Documentation
- **Type:** New documentation
- **File:** `docs/sandbox_manager.md`
- **Problem:** Zero standalone documentation existed for the sandbox manager subsystem.
- **Action:** Created comprehensive documentation covering:
  - Architecture diagram (Manager → LanguagePool → SandboxContainer hierarchy)
  - Full lifecycle (startup → orphan cleanup → pool creation → monitor thread → shutdown)
  - Request flow (acquire → prepare_workdir → run_command → release/destroy)
  - Configuration reference (`sandbox_config.yml` schema with sizing guidelines)
  - Scaling behavior diagram (pool_size → scale_limit with auto scale-up/down)
  - Complete SandboxContainer API (`prepare_workdir`, `run_command`, `run_commands`, `make_request`)
  - All enums (Language with Docker images, SandboxState, ResponseCategory)
  - CommandResponse dataclass
  - Docker image listing and container security constraints
  - Usage patterns (direct, context manager, destroy on error)
  - Monitoring (pool stats, load warnings)
- **Status:** ✅ Done

#### Item 11: Create Documentation Index Page
- **Type:** New documentation
- **File:** `docs/index.md`
- **Problem:** No single entry point listing all available documentation. Users must navigate via README links (some of which are broken) or know file names.
- **Action:** Create a structured index page categorizing all docs (Getting Started, API Reference, Features, Architecture, Development).
- **Status:** ✅ Done

---

### 🟢 Priority 3 — Cleanup & Consolidation

#### Item 12: Archive or Consolidate Internal Implementation Summaries
- **Type:** Cleanup
- **Files:** `docs/DCE_IMPLEMENTATION_SUMMARY.md`, `docs/NEW_FEATURES.md`, `docs/web_refactoring.md`, `WEB_REFACTORING_SUMMARY.md`
- **Problem:** These are internal development logs, not user-facing documentation:
  - `DCE_IMPLEMENTATION_SUMMARY.md` — 268-line changelog of files created/modified for DCE
  - `NEW_FEATURES.md` — 835-line feature planning document (some specs are outdated vs actual implementation)
  - `web_refactoring.md` — Empty file
  - `WEB_REFACTORING_SUMMARY.md` — Empty file (in project root, not docs/)
- **Action:** Extract any useful content into canonical docs, then move these to a `docs/archive/` folder or delete them.
- **Status:** ✅ Done

#### Item 13: Reconcile `web/README.md` with Main Documentation
- **Type:** Consolidation
- **Files:** `web/README.md`, new `docs/web_module.md`
- **Problem:** The web README contained deployment, configuration, and troubleshooting information that overlapped with but also supplemented `docs/API.md` and `docs/development.md`. This created confusion about which doc was authoritative.
- **Action:** Migrated core architecture, configuration, deployment, and troubleshooting content into `docs/web_module.md`. Added cross-reference banner to `web/README.md` pointing to main docs. The web README is kept as a quick-reference for developers working directly in the `web/` module.
- **Status:** ✅ Done

#### Item 14: Update `multi_language_support.md` Field Names
- **Type:** Fix existing doc
- **File:** `docs/multi_language_support.md`
- **Problem:** Uses old single-`language` field in API examples. Actual schema uses `languages: List[str]` (plural, list). Also uses `assignment_id` instead of `external_assignment_id`.
- **Action:** Update all API examples in the document to use current schema field names.
- **Status:** ✅ Done

#### Item 15: Update `setup_config_feature.md` Examples
- **Type:** Fix existing doc
- **File:** `docs/setup_config_feature.md`
- **Problem:** Uses `"language": "java"` (old single-field format) and shows `setup_commands` as plain strings in some examples vs named objects in others. References non-existent `example_java_config_with_setup.json`. The document also does not reflect the current language-specific setup config format where each language has its own `required_files` and `setup_commands` block (e.g., `{"python": {...}, "java": {...}}`).
- **Action:** Rewrite the document to reflect the current `PreFlightService._resolve_setup_config()` behavior, which expects a language-keyed dictionary. Update all examples to use the multi-language setup config format.
- **Status:** ✅ Done

#### Item 16: Remove Empty Documentation Directories
- **Type:** Cleanup
- **Files:** `docs/core/`, `docs/configuration/`, `docs/algorithms/`, `docs/sandbox/`, `docs/api/`, `docs/services/`, `docs/reference/`
- **Problem:** Seven empty subdirectories exist under `docs/` with no content. These were likely created as placeholders for a planned documentation restructure that never materialized. They create confusion about where documentation should live and suggest a structure that doesn't match reality.
- **Action:** Delete all empty directories. If a future restructure is desired, it should be planned holistically (see Item 19) rather than leaving empty shells.
- **Status:** ✅ Done

---

### 🔵 Priority 4 — Enhancement & Agent Skills

#### Item 17: Create Agent Skill Documents for Code Navigation
- **Type:** New documentation (agent-oriented)
- **Files:** Create `.github/copilot-instructions.md` or similar agent skill files
- **Problem:** AI agents working through the code lack contextual knowledge of project conventions, architecture patterns, and component relationships.
- **Action:** Create agent-oriented skill documents covering:
  - Project architecture overview (pipeline pattern, service layer, repository pattern)
  - How to add a new API endpoint (route → schema → service → repository flow)
  - How to add a new grading template (TestFunction abstract class → template library → registration)
  - How to add a new sandbox language (Language enum → Docker image → pool config)
  - Common debugging patterns and log locations
  - Testing conventions (unit vs integration vs web tests)
- **Status:** ✅ Done

#### Item 18: Automated Documentation Validation
- **Type:** Enhancement / CI
- **Problem:** Documentation drifts from code because there's no automated validation. Links break, schema examples become outdated, and endpoint paths fall out of sync with actual routes.
- **Action:** Build a validation script (`scripts/validate_docs.py` or similar) and integrate it into CI. The script should check:
  1. **Broken link detection** — Scan all `.md` files for relative links and verify each target file exists on disk. Flag any dead links.
  2. **Endpoint path validation** — Extract all HTTP paths referenced in `docs/API.md` (e.g., `POST /api/v1/configs`) and cross-reference them against actual FastAPI route registrations in `web/api/v1/`. Flag any documented paths that don't exist or any registered routes that are undocumented.
  3. **Schema field validation** — Parse request/response JSON examples in `docs/API.md` and compare top-level field names against the corresponding Pydantic model fields in `web/schemas/`. Flag mismatched, missing, or extra fields.
  4. **CI integration** — Run the validation as a GitHub Actions step on every PR that modifies files in `docs/` or `web/schemas/` or `web/api/`. Fail the check if any issues are found.
- **Output:** The script should produce a clear report listing each issue with the file, line number, and description of the mismatch.
- **Status:** ✅ Done

#### Item 19: Restructure Documentation Directory Layout
- **Type:** Enhancement
- **Problem:** Documentation files are flat in `docs/` with no logical grouping. Feature docs (`focus_feature.md`, `setup_config_feature.md`, `multi_language_support.md`), architecture docs (`core_structures.md`, `sandbox_manager.md`), API docs (`API.md`), and planning docs (`NEW_FEATURES.md`, `DOCUMENTATION_MODERNIZATION_ROADMAP.md`) all sit at the same level. The `docs/index.md` provides a table-based index, but the filesystem itself doesn't reflect the categories.
- **Action:** After all content fixes are complete (Items 12–15), reorganize into a clear directory structure:
  - `docs/architecture/` — `core_structures.md`, `sandbox_manager.md`, `web_module.md`, `pipeline_execution_tracking.md`
  - `docs/features/` — `setup_config_feature.md`, `focus_feature.md`, `multi_language_support.md`, `deliberate_code_execution.md`
  - `docs/api/` — `API.md`, quick-start guides
  - `docs/templates/` — Already exists, keep as-is
  - `docs/guides/` — `development.md`, `configuration_examples.md`
  - `docs/roadmaps/` — This file, `TECHNICAL_DEBT_ROADMAP.md`
  - Update `docs/index.md` and all cross-references accordingly.
- **Status:** ✅ Done

---

## Progress Tracking

| # | Item | Priority | Status |
|---|------|----------|--------|
| 1 | DCE in API docs | 🔴 P1 | ✅ Done |
| 2 | Fix endpoint paths | 🔴 P1 | ✅ Done |
| 3 | Fix submission schema | 🔴 P1 | ✅ Done |
| 4 | Remove fictional features | 🔴 P1 | ✅ Done |
| 5 | Add missing endpoints | 🔴 P1 | ✅ Done |
| 6 | Fix DCE schema mismatch | 🔴 P1 | ✅ Done |
| 7 | Fix core structures doc | 🔴 P1 | ✅ Done |
| 8 | Fix broken links | 🟡 P2 | ✅ Done |
| 9 | Template library docs | 🟡 P2 | ✅ Done |
| 10 | Sandbox manager docs | 🟡 P2 | ✅ Done |
| 11 | Documentation index | 🟡 P2 | ✅ Done |
| 12 | Archive impl summaries | 🟢 P3 | ✅ Done |
| 13 | Reconcile web/README | 🟢 P3 | ✅ Done |
| 14 | Fix multi-language doc | 🟢 P3 | ✅ Done |
| 15 | Fix setup config doc | 🟢 P3 | ✅ Done |
| 16 | Remove empty doc dirs | 🟢 P3 | ✅ Done |
| 17 | Agent skill documents | 🔵 P4 | ✅ Done |
| 18 | Automated doc validation | 🔵 P4 | ✅ Done |
| 19 | Restructure docs layout | 🔵 P4 | ✅ Done |









