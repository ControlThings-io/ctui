# ctui examples

Each example introduces only a small part of the library. Read and run them in
this order:

1. `01_first_command.py` — create your first class-based `@command`.
2. `02_class_application.py` — organize commands in a `CtuiApp` subclass.
3. `03_types_and_options.py` — parse types, defaults, choices, and flags.
4. `04_completion_and_validation.py` — create safe dropdown suggestions.
5. `05_async_and_events.py` — run overlapping async commands and show immediate
   started/completed messages.
6. `06_footer_progress.py` — track several active commands in the status bar
   and remove each one when it finishes.
7. `07_headless_testing.py` — use the automatic traditional CLI shared by every
   `CtuiApp`.
8. `filesystem.py` — combine several features in a practical tool.

Run an example from the repository root:

```bash
uv run examples/01_first_command.py
```

Every terminal example includes commands to try in its opening docstring. The
headless example accepts commands after its filename. Start with:

```bash
uv run examples/07_headless_testing.py --help
uv run examples/07_headless_testing.py -c "add 12 30"
uv run examples/07_headless_testing.py --file examples/commands.txt
```
