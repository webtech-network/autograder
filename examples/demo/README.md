# Browser demo

Start the local API (`make start-autograder`), then run `make examples-demo`
and open `http://localhost:8080/demo/`. The demo server also serves the
checked-in definitions and student programs under `examples/assets/` that the
demo loads. Configuration, submission and polling requests use the v1
integration contracts.

Enter the API's address and its integration token on the landing page. Every
request the demo makes except the health check and the template catalog,
including polling a submission, requires that token
([AUTH.md](../../docs/contracts/AUTH.md)). See the
[examples overview](../README.md).
