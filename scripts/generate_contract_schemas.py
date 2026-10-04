#!/usr/bin/env python3
"""Regenerate the checked-in authoring and terminal wire schemas from core models."""
import json
from pathlib import Path
from autograder import grading_definition_json_schema, outcome_json_schema


def main():
    root = Path(__file__).resolve().parents[1] / 'docs' / 'contracts' / 'v1'
    root.mkdir(parents=True, exist_ok=True)
    for name, schema in [('grading-definition', grading_definition_json_schema()),
                         ('terminal-outcome', outcome_json_schema())]:
        (root / f'{name}.schema.json').write_text(
            json.dumps(schema, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
