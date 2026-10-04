# Browser demo

Start the local API, then run `python examples/demo/serve_demo.py` from the
repository root and open `http://localhost:8080/demo/`. The server also exposes
checked-in definitions/student sources used by the demo. Configuration, PATCH,
submission and polling requests use the canonical v1 integration contracts.

Set the API base URL and its integration token on the landing page. Full outcome
details require that token; compact status polling does not. See the
[example instructions](../README.md).
