# Feature Roadmap

**Created:** March 18, 2026
**Status:** Planning
**Purpose:** Outline planned features for the Autograder, describing what each feature brings to the platform and its priority.

---

## Context

The Autograder is a pipeline-based grading system where submissions flow through a criteria tree of categories, subjects, and tests. Today, every grading run traverses the entire tree and produces a single final score. The features in this roadmap aim to expand the platform's capabilities, improve the student experience, and give educators more control over how grading is performed.

---

## Roadmap Items

### Item 1: Partial Grading Execution

- **Priority:** TBD
- **Summary:** Allow users to scope a grading run to a subset of the criteria tree instead of always executing the full tree.

#### Description

Currently, the autograder traverses the entire criteria tree for every submission — all categories, all subjects, all tests. The final score reflects everything, with no way to say "just grade this part." This means a student who has only worked on one aspect of an assignment (e.g., the HTML portion of an HTML/CSS/JS project) will see a low overall score because the unfinished parts drag it down. This can be demotivating.

Partial grading execution lets the user select a scope — a specific category, subject, or set of tests — and the pipeline will only traverse and score that portion of the tree. The result reflects only the selected scope, while ungraded parts appear as "not yet graded" placeholders. This gives students a clear progress map: scored results for what they've tackled, and visible indicators for what's left.

#### Motivation

- **Incremental workflow:** Students can work on an assignment piece by piece, getting meaningful feedback at each step without being penalized for unfinished sections.
- **Gamification:** Subjects become "phases" in a journey. Students can treat each subject as a milestone to complete before moving on to the next, turning assignments into a progression-based experience.
- **Reduced demotivation:** A student focusing on HTML for the day sees "HTML: 85/100, CSS: not yet graded, JS: not yet graded" instead of a discouraging overall score of 30/100.
- **Student autonomy:** Students control their own pacing and can choose what to focus on and when to get feedback.

#### Related Extensions

- **Prerequisite Chains:** Educators could define dependencies between subjects or tests in the criteria tree — e.g., "Basic Syntax must be passed before the OOP subject is evaluated." This enforces a learning progression and prevents students from jumping to advanced topics without demonstrating foundational understanding. Combined with partial grading, the system could show locked phases that unlock as prerequisites are met, reinforcing the gamified journey.
- **Time-Aware Grading Windows:** Instead of a single deadline, educators could define grading windows per subject or phase — e.g., "HTML is open for grading this week, CSS opens next week." This structures the assignment as a paced curriculum rather than a single deliverable, giving educators control over the progression rhythm while students still work at their own pace within each window.

---

### Item 2: Collaborative Submissions

- **Priority:** TBD
- **Summary:** Support group assignments where a submission has multiple authors, with individual scores distributed based on each student's actual contribution.

#### Description

Today, submissions follow a strict 1:1 relationship — one student, one submission, one score. This feature changes that model to support group assignments where multiple students collaborate on a single submission.

The key distinction from a simple "shared grade" is that the autograder should evaluate individual contributions and assign scores fairly. If student A implemented the core functionality that made most tests pass while student B contributed minimally, their scores should reflect that difference. The system should be able to trace which contributions led to which test outcomes and weight scores accordingly.

Git and GitHub are likely candidates for tracking contributions, since commit history, authorship, and blame data provide a natural record of who did what. However, the exact mechanism for measuring and attributing contribution is still an open design question.

#### Motivation

- **Real-world collaboration:** Group assignments mirror professional software development, where teams work together on shared codebases.
- **Fair individual assessment:** Instead of giving everyone the same grade, the system rewards students proportionally to their actual contributions.
- **Accountability:** Students know their individual effort will be measured, discouraging free-riding.
- **Richer feedback:** Each student can receive feedback tailored to the parts of the assignment they worked on.

#### Open Challenges

- **Measuring contribution is inherently hard.** Commit count doesn't equal value, lines of code don't equal impact, and some high-value contributions (architecture decisions, debugging, code review) may leave little trace in version history. The contribution evaluation model is a core design challenge within this feature and will need careful thought to avoid rewarding superficial metrics over meaningful work.

---

### Item 3: Static Analysis Grading

- **Priority:** TBD
- **Summary:** Introduce static analysis tests that evaluate code quality, structure, and practices — independent of whether the code runs successfully — to combat the pass/fail dilemma.

#### Description

Currently, most grading tests are execution-based: run the code, check the output. This creates a pass/fail dilemma where a student who wrote excellent, well-structured code but made a minor mistake (a missing comma, a typo in a variable name) can receive zero for an entire test or subject. The code's quality and the student's understanding are invisible to the grader.

Static analysis grading evaluates the code itself — its structure, conventions, and practices — without executing it. This means students can earn points for the quality of their implementation even when their code doesn't compile or produce the correct output.

This feature should work both standalone (an assignment graded purely on code quality) and alongside execution-based tests within the same criteria tree (e.g., a subject for "Functionality" using runtime tests and a subject for "Code Quality" using static analysis).

The analysis should follow a hybrid approach:
- **Language-agnostic checks** that apply to all supported languages: modularity, commenting, naming conventions, code organization, etc.
- **Language-specific checks** that leverage idioms and features of a particular language: e.g., use of duck typing in Python, proper interface usage in Java, etc.

How this integrates with the existing grading template strategy (whether it becomes its own template, a cross-cutting layer, or something else) is an open design question to be explored further.

#### Motivation

- **Fairer grading:** Students are rewarded for understanding and craftsmanship, not just whether their code runs.
- **Fighting the pass/fail dilemma:** A minor syntax error no longer means a zero — the student's effort and approach are still recognized.
- **Teaching good practices:** By explicitly scoring things like modularity, naming, and idiomatic usage, students are incentivized to write better code, not just code that works.
- **Broader assessment:** Educators can evaluate dimensions of student work that execution-based tests simply cannot capture.

#### Open Challenges

- **Integration with the template system.** How static analysis tests fit into the existing grading template strategy needs further discussion — whether as a new template type, an extension to existing templates, or a separate layer that can be composed with any template.
- **Balancing language-agnostic and language-specific checks.** The hybrid approach needs a clear structure so that educators can configure both general and language-specific checks without the system becoming overly complex.

---

### Item 4: Grading Webhooks / Event System

- **Priority:** TBD
- **Summary:** Allow external systems to subscribe to grading events via webhooks, making the autograder more integrable with LMS platforms, notification services, and custom tooling.

#### Description

Currently, grading results are consumed through the REST API or the GitHub Action export. There is no mechanism for external systems to be notified when something happens in the autograder — a submission is received, grading completes, a student crosses a score threshold, etc.

This feature introduces an event system where the autograder emits events at key moments in the grading lifecycle, and external systems can subscribe to those events via webhooks. Educators or platform administrators would configure webhook URLs and select which events they want to receive.

Potential events include:
- **Submission received** — a new submission has been submitted for grading.
- **Grading complete** — a submission has been fully graded, with the result payload included.
- **Score threshold reached** — a student's score crossed a configured threshold (e.g., passed 70%).
- **First submission** — a student submitted for the first time on an assignment.

This opens the door to integrations with learning management systems (Moodle, Canvas), messaging platforms (Slack, Discord), custom dashboards, and any other tooling that educators or institutions use in their workflows.

#### Motivation

- **Broader integration:** The autograder becomes a component in a larger ecosystem rather than a standalone tool, connecting to whatever platforms an institution already uses.
- **Real-time awareness:** Educators can receive notifications when students submit or hit milestones, without polling the API.
- **Custom workflows:** Institutions can build their own automation on top of grading events — e.g., auto-posting results to a class channel, triggering follow-up assignments, or updating grade books.
- **Extensibility without coupling:** New integrations can be added externally by subscribing to webhooks, without modifying the autograder's core code.

---

### Item 5: Assignment Template Marketplace

- **Priority:** TBD
- **Summary:** A shared library where educators can publish, discover, and reuse pre-built grading configurations, turning the community into an adoption engine.

#### Description

Setting up a grading configuration from scratch — defining the criteria tree, choosing tests, tuning weights — takes time and requires familiarity with the autograder's configuration model. Many educators end up building similar configurations for common assignment types (e.g., "Build a REST API," "Create a responsive webpage," "Implement a sorting algorithm"). There's no way to share or reuse that work across educators or institutions.

The template marketplace is a shared repository where educators can publish their grading configurations and discover configurations published by others. A teacher setting up a "Build a REST API in Flask" assignment could search the marketplace, find a community-contributed configuration for that exact scenario, and use it as-is or fork it as a starting point.

Configurations in the marketplace would be tagged and searchable by language, course level, topic, assignment type, and template used. Educators could rate and review configurations, and popular ones would surface naturally.

#### Motivation

- **Lower barrier to entry:** New educators don't have to learn the configuration model from scratch — they can start from a working example and adapt it.
- **Community-driven growth:** Every configuration published makes the platform more valuable for the next teacher. Adoption feeds adoption.
- **Consistency across institutions:** Common assignment types can converge on well-tested, community-vetted grading criteria.
- **Reduced setup time:** Instead of spending time building a criteria tree, educators spend time teaching.
