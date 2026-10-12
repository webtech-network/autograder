# Template resolution at compilation

`compile_definition` resolves canonical built-in identifiers
(`input_output`, `webdev`, `api`, `static_analysis`) or trusted Python
instances supplied through `templates={identifier: instance}`.
It validates each template's registry and parameter contracts before execution.
Uploaded code is unsupported.

The compiled definition retains those instances and embeds evaluator references
in its criteria tree. There is no runtime template attachment operation.
Unknown identifiers and invalid contracts produce `DefinitionValidationError`
before any provider is called.

See [catalog and trusted Python extensions](../contracts/CATALOG.md).
Implementation: `autograder/models/contracts/definition.py` and
`autograder/services/template_library_service.py`.
