# Migration Guide: New Directory Organization

The `/examples/assets/input_output` directory has been reorganized for better clarity and maintainability.

## What Changed?

Files that were previously scattered at the root level have been organized into logical subdirectories:

### Old Structure → New Structure

```
Old:                              New:
input_output/                     input_output/
├── index.html              →     ├── dashboard/
├── page_*.html             →     │   ├── index.html
├── styles.css              →     │   ├── page_*.html
├── shared.js               →     │   ├── styles.css
├── serve_dashboard.py      →     │   └── shared.js
├── validate_criteria.py    →     ├── scripts/
├── calculator.py           →     │   ├── serve_dashboard.py
├── criteria.json           →     │   ├── validate_criteria.py
├── feedback.json           →     │   └── calculator.py
├── setup.json              →     ├── sample_files/
├── requirements.txt        →     │   ├── criteria.json
├── criteria_examples/            │   ├── feedback.json
└── code_examples/                │   ├── setup.json
                                  │   └── requirements.txt
                                  ├── criteria_examples/
                                  └── code_examples/
```

## Updated Paths

### Starting the Dashboard

**Old:**
```bash
cd examples/assets/input_output
python serve_dashboard.py
```

**New:**
```bash
cd examples/assets/input_output/scripts
python serve_dashboard.py
```

### File References

| File Type | Old Location | New Location |
|-----------|-------------|--------------|
| HTML files | `input_output/*.html` | `input_output/dashboard/*.html` |
| Scripts | `input_output/*.py` | `input_output/scripts/*.py` |
| Sample configs | `input_output/*.json` | `input_output/sample_files/*.json` |
| Criteria examples | `input_output/criteria_examples/` | (unchanged) |
| Code examples | `input_output/code_examples/` | (unchanged) |

## Benefits

1. **Clearer organization**: Files are grouped by purpose
2. **Better navigation**: Each subdirectory has its own README
3. **Easier maintenance**: Related files are together
4. **Reduced clutter**: Root directory only has README and subdirectories

## Documentation Updates

The following files have been updated to reflect the new structure:
- `examples/assets/input_output/README.md`
- `examples/assets/README.md`
- `docs/setup_config_feature.md`
- `examples/assets/input_output/scripts/serve_dashboard.py`

## No Breaking Changes

The dashboard server automatically serves from the correct location. Just update your command to run it from the `scripts/` directory.

