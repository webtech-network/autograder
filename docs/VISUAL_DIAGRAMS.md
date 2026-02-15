# Autograder System - Visual Diagrams

This document contains visual representations of the Autograder system architecture and workflows.

---

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          AUTOGRADER SYSTEM                                  │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                         WEB API LAYER                                 │ │
│  │                                                                       │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │ │
│  │  │   FastAPI    │  │  PostgreSQL  │  │  Background  │               │ │
│  │  │ REST Server  │─→│   Database   │←─│    Tasks     │               │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘               │ │
│  │         │                  │                  │                       │ │
│  │         │ POST /configs    │ Store configs    │ Async grading        │ │
│  │         │ POST /submit     │ Store results    │ queue processing     │ │
│  │         │                  │                  │                       │ │
│  └─────────┼──────────────────┼──────────────────┼───────────────────────┘ │
│            │                  │                  │                         │
│            ▼                  ▼                  ▼                         │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                      AUTOGRADER CORE                                  │ │
│  │                                                                       │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │ │
│  │  │              AutograderPipeline (Stateless)                     │ │ │
│  │  │  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐   │ │ │
│  │  │  │ Load │→ │Build │→ │ Pre  │→ │Grade │→ │Focus │→ │Feed  │   │ │ │
│  │  │  │Templ.│  │ Tree │  │Flight│  │      │  │      │  │ back │   │ │ │
│  │  │  └──────┘  └──────┘  └──────┘  └──────┘  └──────┘  └──────┘   │ │ │
│  │  └─────────────────────────────────────────────────────────────────┘ │ │
│  │                                                                       │ │
│  │  Services:                                                            │ │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐            │ │
│  │  │ CriteriaTree  │  │    Grader     │  │     Focus     │            │ │
│  │  │   Service     │  │   Service     │  │   Service     │            │ │
│  │  └───────────────┘  └───────────────┘  └───────────────┘            │ │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐            │ │
│  │  │   Reporter    │  │   Template    │  │   PreFlight   │            │ │
│  │  │   Service     │  │   Library     │  │   Service     │            │ │
│  │  └───────────────┘  └───────────────┘  └───────────────┘            │ │
│  │                                                                       │ │
│  │  Templates:                                                           │ │
│  │  [WebDev] [Input/Output] [API Testing] [Essay] [Custom]              │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│            │                                                               │
│            ▼                                                               │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                      SANDBOX MANAGER                                  │ │
│  │                                                                       │ │
│  │  Language Pools:                                                      │ │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐    │ │
│  │  │   Python   │  │    Java    │  │   Node.js  │  │    C++     │    │ │
│  │  │    Pool    │  │    Pool    │  │    Pool    │  │    Pool    │    │ │
│  │  ├────────────┤  ├────────────┤  ├────────────┤  ├────────────┤    │ │
│  │  │ ○ ○ ● ○ ○  │  │ ○ ● ○      │  │ ○ ○ ● ○    │  │ ○ ●        │    │ │
│  │  │ Containers │  │ Containers │  │ Containers │  │ Containers │    │ │
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────┘    │ │
│  │  ○ = idle     ● = in use                                             │ │
│  │                                                                       │ │
│  │  ┌──────────────────────────────────────────────────────────────┐   │ │
│  │  │          Docker Engine (Container Orchestration)             │   │ │
│  │  └──────────────────────────────────────────────────────────────┘   │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘

Legend:
  → : Data flow
  ○ : Idle container
  ● : Active container
```

---

## Pipeline Execution Flow

```
┌───────────────────────────────────────────────────────────────────────────┐
│                          PIPELINE EXECUTION FLOW                          │
└───────────────────────────────────────────────────────────────────────────┘

INPUT: Submission (username, files, language)
  │
  ▼
┌─────────────────────────────────────────┐
│ PipelineExecution.start_execution()     │
│ • Create execution context              │
│ • Status = RUNNING                      │
│ • Add BOOTSTRAP step                    │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│ STEP 1: TemplateLoaderStep              │
│ • Load template from library            │
│ • Get test functions                    │
│ • Return: Template object               │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│ STEP 2: BuildTreeStep                   │
│ • Validate criteria config              │
│ • Match tests to template               │
│ • Build CriteriaTree                    │
│ • Embed test functions in TestNodes     │
│ • Balance weights                       │
│ • Return: CriteriaTree                  │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│ STEP 3: PreFlightStep (optional)        │
│ • Check required files                  │
│ • Create sandbox if needed              │
│ • Run setup commands                    │
│ • Return: SandboxContainer or None      │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│ STEP 4: GradeStep ⭐ CORE STEP          │
│                                         │
│ ┌─────────────────────────────────┐   │
│ │ For each category:              │   │
│ │   For each subject:             │   │
│ │     For each test:              │   │
│ │       1. Get target files       │   │
│ │       2. Execute test function  │   │
│ │       3. Create TestResultNode  │   │
│ │     Calculate subject score     │   │
│ │   Calculate category score      │   │
│ │ Calculate final score           │   │
│ └─────────────────────────────────┘   │
│                                         │
│ • Return: ResultTree + final_score     │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│ STEP 5: FocusStep (optional)            │
│ • Calculate impact of each test         │
│ • Sort by impact (highest first)        │
│ • Return: Focus (prioritized tests)     │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│ STEP 6: FeedbackStep (optional)         │
│ • Generate feedback (default or AI)     │
│ • Use focused tests                     │
│ • Return: Feedback text                 │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│ STEP 7: ExporterStep (optional)         │
│ • Export to external systems            │
│ • Return: Export confirmation           │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│ PipelineExecution.finish_execution()    │
│ • Set status = SUCCESS or FAILED        │
│ • Create GradingResult object           │
│ • Cleanup sandbox                       │
└─────────────┬───────────────────────────┘
              │
              ▼
OUTPUT: PipelineExecution
  • status: SUCCESS/FAILED/INTERRUPTED
  • result: GradingResult
    - final_score: 0-100
    - feedback: string
    - result_tree: ResultTree
```

---

## Criteria Tree Structure

```
┌──────────────────────────────────────────────────────────────────────┐
│                          CRITERIA TREE                               │
│                      (Stateless Definition)                          │
└──────────────────────────────────────────────────────────────────────┘

                         CriteriaTree (Root)
                                │
                ┌───────────────┼───────────────┐
                │               │               │
          ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐
          │   BASE     │  │   BONUS   │  │  PENALTY  │
          │ (required) │  │ (optional)│  │ (optional)│
          │ weight=100 │  │ weight=20 │  │ weight=10 │
          └─────┬──────┘  └─────┬─────┘  └─────┬─────┘
                │               │               │
        ┌───────┼───────┐       │               │
        │       │       │       │               │
   ┌────▼──┐ ┌─▼───┐ ┌─▼───┐  │               │
   │Subject│ │Subj │ │Subj │  │               │
   │  1    │ │  2  │ │  3  │  │               │
   │ w=40  │ │ w=40│ │ w=20│  │               │
   └───┬───┘ └──┬──┘ └──┬──┘  │               │
       │        │       │      │               │
   ┌───┴───┐   │    ┌──┴───┐  │          ┌────▼─────┐
   │       │   │    │      │  │          │  Test    │
┌──▼──┐ ┌─▼──┐│ ┌──▼──┐ ┌─▼──┐       │  (direct) │
│Test │ │Test││ │Test │ │Test│       └──────────┘
│  1  │ │  2 ││ │  3  │ │  4 │
└─────┘ └────┘│ └─────┘ └────┘
              │
         ┌────┴─────┐
         │Recursive │
         │ Subjects │
         └──────────┘

Node Types:
┌────────────────────────────────────────────────────────┐
│ CategoryNode                                           │
│ • name: "base" | "bonus" | "penalty"                   │
│ • weight: float                                        │
│ • subjects: List[SubjectNode]                          │
│ • tests: List[TestNode]                                │
│ • subjects_weight: Optional[float]                     │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│ SubjectNode (Recursive)                                │
│ • name: string                                         │
│ • weight: float                                        │
│ • subjects: List[SubjectNode] ← Can nest!              │
│ • tests: List[TestNode]                                │
│ • subjects_weight: Optional[float]                     │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│ TestNode (Leaf)                                        │
│ • name: string                                         │
│ • test_function: TestFunction ← EMBEDDED!              │
│ • parameters: Dict[str, Any]                           │
│ • file_target: Optional[List[str]]                     │
│ • weight: float                                        │
└────────────────────────────────────────────────────────┘
```

---

## Result Tree Structure

```
┌──────────────────────────────────────────────────────────────────────┐
│                           RESULT TREE                                │
│                       (Stateful Execution)                           │
└──────────────────────────────────────────────────────────────────────┘

                         ResultTree
                             │
                      ┌──────▼──────┐
                      │RootResultNode│
                      │ score: 85.5  │
                      └──────┬───────┘
                ┌────────────┼────────────┐
                │            │            │
        ┌───────▼──────┐ ┌──▼──────┐ ┌──▼────────┐
        │CategoryResult│ │Category │ │ Category  │
        │   BASE       │ │ BONUS   │ │  PENALTY  │
        │ score: 75.0  │ │score:80 │ │ score: 30 │
        └───────┬──────┘ └─────────┘ └───────────┘
                │
        ┌───────┼───────┐
        │       │       │
   ┌────▼───┐ ┌▼────┐ ┌▼────┐
   │Subject │ │Subj │ │Subj │
   │Result 1│ │Res 2│ │Res 3│
   │ s=87.5 │ │s=50 │ │s=90 │
   └────┬───┘ └─────┘ └─────┘
        │
   ┌────┴────┐
   │         │
┌──▼────┐ ┌─▼─────┐
│ Test  │ │ Test  │
│Result1│ │Result2│
│ s=100 │ │ s=75  │
│ "✓"   │ │ "4/5" │
└───────┘ └───────┘

Score Calculation (Bottom-Up):

1. Leaf Level (Tests):
   TestResult1: score = 100
   TestResult2: score = 75

2. Subject Level:
   Subject1.score = (100 * 50 + 75 * 50) / 100 = 87.5

3. Category Level:
   Base.score = (87.5 * 60 + 50 * 40) / 100 = 72.5

4. Root Level (Special):
   base_score = 72.5
   bonus_points = (80/100) * 20 = 16
   penalty_points = (30/100) * 10 = 3
   final = 72.5 + 16 - 3 = 85.5
```

---

## Weight Balancing Algorithm

```
┌──────────────────────���───────────────────────────────────────┐
│               WEIGHT BALANCING ALGORITHM                     │
└──────────────────────────────────────────────────────────────┘

Input: Siblings with arbitrary weights
┌──────────┐  ┌──────────┐  ┌──────────┐
│Subject A │  │Subject B │  │Subject C │
│ weight=60│  │ weight=80│  │ weight=40│
└──────────┘  └──────────┘  └──────────┘
Total: 60 + 80 + 40 = 180

Algorithm:
1. Calculate total weight: 180
2. Calculate scaling factor: 100 / 180 = 0.556
3. Multiply each weight by factor:
   - A: 60 * 0.556 = 33.33
   - B: 80 * 0.556 = 44.44
   - C: 40 * 0.556 = 22.22

Output: Balanced weights sum to 100
┌──────────┐  ┌──────────┐  ┌──────────┐
│Subject A │  │Subject B │  │Subject C │
│ w=33.33  │  │ w=44.44  │  │ w=22.22  │
└──────────┘  └──────────┘  └──────────┘
Total: 33.33 + 44.44 + 22.22 = 100 ✓
```

---

## Heterogeneous Tree Example

```
┌──────────────────────────────────────────────────────────────┐
│            HETEROGENEOUS TREE (Mixed Structure)              │
└──────────────────────────────────────────────────────────────┘

                    SubjectNode "HTML"
                    weight: 100
                    subjects_weight: 70%
                           │
           ┌───────────────┼───────────────┐
           │               │               │
      SUBJECTS (70%)       │          TESTS (30%)
           │               │               │
      ┌────┴─────┐        │          ┌────┴─────┐
      │          │        │          │          │
  ┌───▼───┐  ┌──▼───┐   │      ┌───▼───┐  ┌──▼───┐
  │Subject│  │Subject│   │      │ Test  │  │ Test │
  │   1   │  │   2   │   │      │   A   │  │   B  │
  │ w=50  │  │ w=50  │   │      │ w=60  │  │ w=40 │
  └───────┘  └──────┘   │      └───────┘  └──────┘
                        │
                        │
Weight Distribution:
┌─────────────────────────────────────────────────────┐
│ Subjects Group: 70% of parent                       │
│   Subject 1: 50% of 70% = 35%                       │
│   Subject 2: 50% of 70% = 35%                       │
│                                                     │
│ Tests Group: 30% of parent                          │
│   Test A: 60% of 30% = 18%                          │
│   Test B: 40% of 30% = 12%                          │
│                                                     │
│ Total: 35 + 35 + 18 + 12 = 100% ✓                   │
└─────────────────────────────────────────────────────┘
```

---

## Focus Service Algorithm

```
┌──────────────────────────────────────────────────────────────┐
│              FOCUS SERVICE (Impact Calculation)              │
└──────────────────────────────────────────────────────────────┘

Goal: Calculate how many points each failed test cost

Example Tree:
                    Base (100%)
                        │
            ┌───────────┴───────────┐
            │                       │
      Subject A (60%)          Subject B (40%)
            │                       │
    ┌───────┴───────┐              │
    │               │              │
Test 1 (50%)    Test 2 (50%)   Test 3 (100%)
score=50        score=100      score=80

Impact Calculation:

Test 1:
  points_missed = 100 - 50 = 50
  weight_factor = 0.50 (test) * 0.60 (subject) * 1.0 (category)
  impact = 50 * 0.30 = 15 points lost ← HIGHEST

Test 2:
  points_missed = 100 - 100 = 0
  impact = 0 points lost

Test 3:
  points_missed = 100 - 80 = 20
  weight_factor = 1.0 (test) * 0.40 (subject) * 1.0 (category)
  impact = 20 * 0.40 = 8 points lost

Focused Output (sorted by impact):
┌────────────────────────────────────────┐
│ 1. Test 1: 15 points lost ⚠️           │
│ 2. Test 3: 8 points lost               │
│ 3. Test 2: 0 points lost ✓             │
└────────────────────────────────────────┘
```

---

## Sandbox Pool Management

```
┌──────────────────────────────────────────────────────────────┐
│                  SANDBOX POOL LIFECYCLE                      │
└──────────────────────────────────────────────────────────────┘

INITIALIZATION:
┌─────────────────────────────────────────────────────────────┐
│ 1. Load config from sandbox_config.yml                     │
│    - PYTHON: min=2, max=5                                  │
│    - JAVA: min=1, max=3                                    │
│    - NODE: min=2, max=4                                    │
│    - CPP: min=1, max=2                                     │
│                                                             │
│ 2. Cleanup orphaned containers from previous runs          │
│                                                             │
│ 3. Create LanguagePool for each language                   │
│                                                             │
│ 4. Pre-warm: Create minimum containers                     │
│    PYTHON: [●][●]                                          │
│    JAVA:   [●]                                             │
│    NODE:   [●][●]                                          │
│    CPP:    [●]                                             │
│                                                             │
│ 5. Start monitor thread (background)                       │
└─────────────────────────────────────────────────────────────┘

ACQUIRE:
┌─────────────────────────────────────────────────────────────┐
│ PreFlightStep needs sandbox                                 │
│         │                                                    │
│         ▼                                                    │
│ get_sandbox(Language.PYTHON)                               │
│         │                                                    │
│         ├─→ Check pool for available container              │
│         │   ┌─ Available? → Mark in-use, return             │
│         │   └─ None available?                              │
│         │       ├─ Below max? → Create new, return          │
│         │       └─ At max? → WAIT for release               │
│         │                                                    │
│         ▼                                                    │
│ SandboxContainer returned                                   │
│         │                                                    │
│         ▼                                                    │
│ Copy submission files                                       │
│ Run setup commands                                          │
│ Execute tests                                               │
└─────────────────────────────────────────────────────────────┘

RELEASE:
┌─────────────────────────────────────────────────────────────┐
│ Pipeline cleanup (after grading)                            │
│         │                                                    │
│         ▼                                                    │
│ release_sandbox(Language.PYTHON, container)                │
│         │                                                    │
│         ├─→ Clean container (remove files)                  │
│         ├─→ Mark as available                               │
│         └─→ Notify waiting threads                          │
│                                                             │
│ Container back in pool: [●] → [○]                           │
└─────────────────────────────────────────────────────────────┘

MONITORING:
┌─────────────────────────────────────────────────────────────┐
│ Background thread runs every 5 seconds                      │
│                                                             │
│ For each pool:                                              │
│   if available < min:                                       │
│       create_container()                                    │
│       add_to_pool()                                         │
│                                                             │
│ Ensures pools always have minimum containers ready          │
└─────────────────────────────────────────────────────────────┘

SHUTDOWN:
┌─────────────────────────────────────────────────────────────┐
│ Application shutdown triggered                              │
│         │                                                    │
│         ▼                                                    │
│ For each pool:                                              │
│   For each container:                                       │
│     container.stop()                                        │
│     container.remove()                                      │
│                                                             │
│ All containers destroyed                                    │
└─────────────────────────────────────────────────────────────┘

Pool State Diagram:
Time →
T0: [○][○]           (min=2, available=2, in_use=0)
T1: [●][○]           (acquire 1)
T2: [●][●]           (acquire 2)
T3: [●][●][●]        (acquire 3, create new)
T4: [●][●][●][●]     (acquire 4, create new)
T5: [●][●][●][●][●]  (acquire 5, at max!)
T6: [○][●][●][●][●]  (release 1)
T7: [○][○][●][●][●]  (release 2)
```

---

## Web API Request Flow

```
┌──────────────────────────────────────────────────────────────┐
│              WEB API REQUEST FLOW                            │
└──────────────────────────────────────────────────────────────┘

PHASE 1: Create Grading Configuration
┌─────────────────────────────────────────────────────────────┐
│ Client                                                       │
│   │                                                          │
│   ├─→ POST /grading-configs                                 │
│   │   {                                                      │
│   │     "external_assignment_id": "hw1",                    │
│   │     "template_name": "webdev",                          │
│   │     "criteria_config": {...},                           │
│   │     "language": null                                    │
│   │   }                                                      │
│   │                                                          │
│   ▼                                                          │
│ FastAPI                                                      │
│   │                                                          │
│   ├─→ Validate criteria config (Pydantic)                   │
│   ├─→ Insert into database                                  │
│   │   grading_configurations table                          │
│   │                                                          │
│   ▼                                                          │
│ Response                                                     │
│   {                                                          │
│     "id": 1,                                                 │
│     "version": 1,                                            │
│     "status": "active"                                       │
│   }                                                          │
└─────────────────────────────────────────────────────────────┘

PHASE 2: Submit Student Work
┌─────────────────────────────────────────────────────────────┐
│ Client                                                       │
│   │                                                          │
│   ├─→ POST /submissions                                     │
│   │   {                                                      │
│   │     "external_assignment_id": "hw1",                    │
│   │     "username": "john.doe",                             │
│   │     "external_user_id": "student123",                   │
│   │     "submission_files": {                               │
│   │       "index.html": "...",                              │
│   │       "style.css": "..."                                │
│   │     }                                                    │
│   │   }                                                      │
│   │                                                          │
│   ▼                                                          │
│ FastAPI                                                      │
│   │                                                          │
│   ├─→ Lookup grading config by external_assignment_id       │
│   ├─→ Insert into submissions table                         │
│   │   status = PENDING                                      │
│   ├─→ Queue background task                                 │
│   │                                                          │
│   ▼                                                          │
│ Response (immediate)                                         │
│   {                                                          │
│     "submission_id": 42,                                     │
│     "status": "PENDING",                                     │
│     "message": "Queued for grading"                          │
│   }                                                          │
└─────────────────────────────────────────────────────────────┘

PHASE 3: Background Grading
┌─────────────────────────────────────────────────────────────┐
│ Background Task                                              │
│   │                                                          │
│   ├─→ Update status = PROCESSING                            │
│   │                                                          │
│   ├─→ Build pipeline from config                            │
│   │   - Load template                                       │
│   │   - Build criteria tree                                 │
│   │   - Add steps                                           │
│   │                                                          │
│   ├─→ Create Submission object                              │
│   │                                                          │
│   ├─→ Run pipeline.run(submission)                          │
│   │   [All pipeline steps execute]                          │
│   │                                                          │
│   ├─→ Extract results                                       │
│   │   - final_score                                         │
│   │   - feedback                                            │
│   │   - result_tree                                         │
│   │                                                          │
│   ├─→ Insert into results table                             │
│   │   - submission_id                                       │
│   │   - final_score                                         │
│   │   - feedback                                            │
│   │   - result_tree (JSON)                                  │
│   │   - execution_time_ms                                   │
│   │   - pipeline_status                                     │
│   │                                                          │
│   └─→ Update submission status = COMPLETED                  │
└─────────────────────────────────────────────────────────────┘

PHASE 4: Retrieve Results
┌─────────────────────────────────────────────────────────────┐
│ Client                                                       │
│   │                                                          │
│   ├─→ GET /submissions/42/results                           │
│   │                                                          │
│   ▼                                                          │
│ FastAPI                                                      │
│   │                                                          │
│   ├─→ Query results table by submission_id                  │
│   │                                                          │
│   ▼                                                          │
│ Response                                                     │
│   {                                                          │
│     "submission_id": 42,                                     │
│     "status": "COMPLETED",                                   │
│     "final_score": 85.5,                                     │
│     "feedback": "...",                                       │
│     "result_tree": {...},                                    │
│     "execution_time_ms": 1234,                               │
│     "graded_at": "2026-02-15T10:30:00Z"                      │
│   }                                                          │
└─────────────────────────────────────────────────────────────┘
```

---

## Template Test Function Execution

```
┌──────────────────────────────────────────────────────────────┐
│           TEST FUNCTION EXECUTION FLOW                       │
└──────────────────────────────────────────────────────────────┘

Example: has_tag test for HTML validation

Step 1: Test Node Created During Tree Building
┌─────────────────────────────────────────────────────────────┐
│ TestNode {                                                   │
│   name: "has_tag"                                           │
│   test_function: <HasTag instance> ← EMBEDDED               │
│   parameters: {                                             │
│     "tag": "nav",                                           │
│     "required_count": 1                                     │
│   }                                                          │
│   file_target: ["index.html"]                              │
│ }                                                            │
└─────────────────────────────────────────────────────────────┘

Step 2: Grading Time - GraderService
┌─────────────────────────────────────────────────────────────┐
│ process_test(test_node):                                    │
│                                                             │
│   1. Get target files                                       │
│      files = get_file_target(["index.html"])              │
│      → [SubmissionFile("index.html", "<html>...")]         │
│                                                             │
│   2. Execute test function                                  │
│      result = test_node.test_function.execute(             │
│          files=files,                                       │
│          sandbox=None,  # No sandbox for webdev            │
│          tag="nav",     # From parameters                  │
│          required_count=1                                   │
│      )                                                      │
│                                                             │
│   3. Inside HasTag.execute():                              │
│      ┌───────────────────────────────────────────────┐    │
│      │ html_content = files[0].content                │    │
│      │ soup = BeautifulSoup(html_content, 'html.parser')│  │
│      │ found_count = len(soup.find_all("nav"))        │    │
│      │ # found_count = 1                               │    │
│      │                                                 │    │
│      │ score = min(100, (1/1)*100) = 100              │    │
│      │ report = "Found 1/1 <nav> tags"                │    │
│      │                                                 │    │
│      │ return TestResult(                             │    │
│      │     test_name="has_tag",                       │    │
│      │     score=100,                                 │    │
│      │     report="Found 1/1 <nav> tags",            │    │
│      │     parameters={"tag":"nav", ...}              │    │
│      │ )                                               │    │
│      └───────────────────────────────────────────────┘    │
│                                                             │
│   4. Create result node                                     │
│      return TestResultNode(                                 │
│          name="has_tag",                                    │
│          test_node=test_node,  # Reference to criteria     │
│          score=100,                                         │
│          report="Found 1/1 <nav> tags",                    │
│          weight=100.0,                                      │
│          parameters={"tag":"nav", "required_count":1}      │
│      )                                                      │
└─────────────────────────────────────────────────────────────┘

Comparison: Static vs Sandboxed Execution

Static (WebDev):
┌─────────────────────────────────────────────┐
│ files → BeautifulSoup → Parse → Count      │
│ No sandbox needed                           │
│ Fast (milliseconds)                         │
└─────────────────────────────────────────────┘

Sandboxed (I/O):
┌─────────────────────────────────────────────┐
│ files → Copy to container                   │
│      → Execute in sandbox                   │
│      → Capture stdout                       │
│      → Compare output                       │
│ Requires sandbox                            │
│ Slower (seconds)                            │
└─────────────────────────────────────────────┘
```

---

This visual documentation complements the main technical documentation by providing clear diagrams of:

1. **System Architecture** - Overall component layout
2. **Pipeline Flow** - Step-by-step execution
3. **Tree Structures** - Criteria and Result trees
4. **Algorithms** - Weight balancing, focus calculation
5. **Sandbox Management** - Pool lifecycle
6. **API Flow** - Request/response patterns
7. **Test Execution** - Function invocation flow

Use these diagrams when:
- Onboarding new developers
- Debugging complex issues
- Understanding data flow
- Designing new features
- Explaining the system to stakeholders

