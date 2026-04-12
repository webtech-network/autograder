# Local Docs Development (MkDocs)

This project uses **MkDocs Material** to publish the documentation website.

## Run locally

```bash
pip install -r requirements-docs.txt
mkdocs serve
```

Open `http://127.0.0.1:8000` to preview changes with live reload.

## Build locally

```bash
mkdocs build --strict
```

`--strict` turns warnings into errors, which helps catch broken navigation or links before opening a PR.

## Where to edit

- Main landing page: `docs/index.md`
- Core concept pages: `docs/core/`
- Pipeline deep dives: `docs/pipeline/`
- Architecture references: `docs/architecture/`
- Roadmaps: `docs/roadmaps/`

## Documentation standards

Every new technical page should follow this teaching pattern:

1. **What it is**
2. **Why it matters**
3. **How it works**
4. **Concrete example**
5. **Common mistakes**

For rubric quality guidance, use [Educational Criteria Design](../guides/criteria-tree-educational-standards.md).
