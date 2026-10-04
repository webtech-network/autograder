# Runnable grading examples

`assets/input_output/criteria_examples/` contains five complete v1 definitions,
from flat addition checks to weighted nested calculator groups. Web and API
examples use `assets/web_dev/definition.json` and `assets/api_testing/definition.json`.
Student sample sources remain under `assets/input_output/code_examples/`.

Validate all calculator definitions from the repository root:

```sh
python examples/assets/input_output/scripts/validate_criteria.py
```

The [contract fixtures](../docs/contracts/DEFINITIONS.md#examples-and-errors) also
cover C, artifacts, AI/static analysis and invalid authoring examples. Old split
criteria/setup/feedback files were retired; use the explicit offline converter.

For the browser demo, start the API (`uvicorn web.main:app`) and run
`python examples/demo/serve_demo.py`. Open `http://localhost:8080/demo/`. The demo
loads the same checked-in definitions, creates canonical configuration envelopes,
submits real files and polls compact results. Supply the configured integration
token on the landing page to fetch protected outcome details. The token stays in
session storage. Required language commands/setup follow the selected languages.

`assets/curl_examples.sh validate-io` exercises validation without saving;
`create-io` and `create-web` create configuration resources on the chosen API.
Configure `AUTOGRADER_API_URL` to change its base URL.
