# Step 4: Preparation

`PreFlightStep` consumes the definition's typed `Preparation` directly. It stages
trusted fixtures, runs the selected language's setup commands in order, and starts
and checks an assessed server when a server capability was selected.

Required source files and criterion targets have already been validated before
provider availability checks and acquisition. They are not checked after fetching
fixtures or creating an environment. A language with no selected setup does not
run another language's commands.

The host resolves logical fixture references to bytes. The session stages each
fixture at a relative path under its declared fixture root. Core neither chooses
provider credentials nor converts definition paths into host filesystem paths.
Empty fixture bytes are valid. Fixtures and source inputs have separate roots.

Commands execute through the owned session. The first failed command stops
preparation and assessment; the terminal outcome has null score/tree. Provider
and infrastructure failures use fixed safe errors. The pipeline closes the owned
session on every path before returning its outcome to the adapter.

See [typed preparation](../features/setup_config_feature.md) for a JSON example,
[capabilities](../contracts/CAPABILITIES.md) for ownership and
[outcomes](../contracts/OUTCOMES.md) for the failure matrix. The obsolete
`SetupConfig`, `PreFlightService` and `SandboxService` execution paths are removed.
