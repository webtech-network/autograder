#!/usr/bin/env python3
"""Generate or check the checked-in wire schemas from their typed models."""
import argparse
import json
from pathlib import Path
from autograder import grading_definition_json_schema, outcome_json_schema


def main():
    from web.main import app

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='fail if generated artifacts differ')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / 'docs' / 'contracts' / 'v1'
    root.mkdir(parents=True, exist_ok=True)
    for name, schema in [('grading-definition', grading_definition_json_schema()),
                         ('terminal-outcome', outcome_json_schema()),
                         ('openapi', app.openapi())]:
        suffix = '.json' if name == 'openapi' else '.schema.json'
        path = root / f'{name}{suffix}'
        generated = json.dumps(schema, indent=2, ensure_ascii=False) + '\n'
        if args.check:
            if not path.exists() or path.read_text(encoding='utf-8') != generated:
                parser.error(f'{path} is stale; run python scripts/generate_contract_schemas.py')
        else:
            path.write_text(generated, encoding='utf-8')


if __name__ == '__main__':
    main()
