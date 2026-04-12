# MkDocs Documentation Roadmap

This roadmap defines how we evolve the documentation into a complete teaching-oriented docs portal powered by MkDocs Material.

## Problem statement

The project already has rich technical docs, but discoverability and learning flow are fragmented. We need a structured docs site that serves both newcomers and maintainers while preserving technical depth.

## Approach

Build a layered documentation experience:

1. **Guided learning path** for core concepts
2. **Deep technical references** for architecture and pipeline internals
3. **Operational docs workflow** (local preview, CI validation, GitHub Pages deployment)

## Workstreams

| Workstream | Goal | Status |
|------------|------|--------|
| Foundation | Add MkDocs config, theme, nav, local dev commands | In progress |
| Core Concepts | Create didactic pages for pipeline, criteria, sandbox, templates, feedback | In progress |
| Educational Quality | Add criteria-tree instructional standards guide | In progress |
| CI Quality Gate | Validate links + strict MkDocs build in PR workflows | Pending |
| Hosting | Publish docs to GitHub Pages from main | Pending |
| Content Migration | Continue refining existing feature/architecture pages for consistent teaching pattern | Pending |

## Definition of done

1. Docs portal builds with `mkdocs build --strict`.
2. Core concept pages are linked from home and nav.
3. PRs that change docs run validation and site build checks.
4. Main branch publishes the site automatically.
5. Documentation style remains "what / why / how / example / pitfalls."

## Next migration priorities

1. Normalize older pages to the didactic page pattern.
2. Add architecture diagrams for request and grading flows.
3. Add contribution standards for docs writing and review.
