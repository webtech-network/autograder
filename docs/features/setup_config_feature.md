# Typed assignment preparation

Preparation belongs to the version 1 grading definition. It names required source
files, setup commands and trusted fixture references. The engine consumes this
typed data directly; no `SetupConfig` or `runtime_setup` conversion remains.

```json
{
  "preparation": {
    "languages": {
      "python": {"required_files": ["main.py"], "setup_commands": []},
      "java": {
        "required_files": ["Main.java"],
        "setup_commands": [{"name": "compile", "command": "javac Main.java"}]
      }
    },
    "fixtures": [{"reference": "datasets/example.csv", "path": "example.csv", "read_only": true}]
  }
}
```

This fragment belongs in a complete definition that allows Python and Java.
Only the selected language's requirements and commands apply. Required source
files are checked before any execution or provider acquisition. Commands or
fixtures request an execution session even when every criterion is static.
Fixtures are resolved by a host-supplied function returning bytes and staged
under the session's declared fixture root before setup commands execute.

A failed required setup command stops assessment with null score/tree. A student
compilation failure reported by an evaluator during assessment can instead be a
valid zero. See the [outcome failure matrix](../contracts/OUTCOMES.md).

Use logical fixture references and relative fixture paths. Docker hosts map the
example fixture to `/tmp/app/example.csv`; commands using it must use that root.
Submitted source lives separately under `/app`; generated artifacts are read
through the session after execution. The engine never opens a fixture reference
as an arbitrary path on the HTTP server or chooses S3 credentials.

Migrate old `setup_config` dictionaries and root `assets` fields with the explicit
[definition migration](../contracts/DEFINITIONS.md). Trusted Python extensions
must replace internal `PreFlightService`/`SandboxService` usage with
[host capabilities](../contracts/CAPABILITIES.md). There is no permissive fallback
parser or setup inheritance. See [accepted input](../contracts/SUBMISSIONS.md)
for source roles and limits.
