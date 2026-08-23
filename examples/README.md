# ctui examples

Each example introduces only a small part of the library. Read and run them in
this order:

1. `default.py` — create the smallest possible application.
2. `01_first_command.py` — register a function with `@app.command`.
3. `02_class_application.py` — organize commands in a `CtuiApp` subclass.
4. `03_types_and_options.py` — parse types, defaults, choices, and flags.
5. `04_completion_and_validation.py` — create safe dropdown suggestions.
6. `05_async_and_events.py` — perform async work and publish events.
7. `06_headless_testing.py` — dispatch commands from tests or scripts.
8. `filesystem.py` — combine several features in a practical tool.

Run an example from the repository root:

```bash
uv run examples/01_first_command.py
```

Every terminal example includes commands to try in its opening docstring. The
headless example prints its result directly and exits.
