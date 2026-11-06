# Calculator examples

The five files under `criteria_examples/` are complete normalized grading
definitions. They use explicit criterion IDs and parameter objects. Student
sources under `code_examples/` cover simple and advanced calculators.

Check one and grade a calculator with it from the repository root, for example
`python -m execution_host.check examples/assets/input_output/criteria_examples/1_base_only_simple.json --language python --submission DIR`,
where `DIR` holds `simple_calculator.py` saved as `calculator.py`. See [examples](../../README.md) for HTTP/browser usage and
[the v1 contract](../../../docs/contracts/DEFINITIONS.md) for migration rules.
