# ctui examples

Each example introduces only a small part of the library. Read and run them in
this order:

1. `01_first_command.py` — create your first class-based `@command`.
2. `02_class_application.py` — organize commands in a `CtuiApp` subclass.
3. `03_types_and_options.py` — parse types, defaults, and constrained values.
4. `04_named_arguments.py` — explicitly declare Linux-style short and long
   named arguments.
5. `05_automatic_cli.py` — use the automatic CLI shared by every `CtuiApp`.
6. `06_completion_and_validation.py` — create safe dropdown suggestions.
7. `07_async_and_events.py` — run overlapping async commands and show immediate
   started/completed messages.
8. `08_statusbar_progress.py` — track several active commands in the status bar
   and remove each one when it finishes.
9. `09_keyboard_shortcuts.py` — register an application-wide shortcut.
10. `10_custom_layout.py` — compose a layout from reusable widgets.
11. `11_lifecycle_and_storage.py` — persist projects, configs, and records.
12. `filesystem.py` — combine several features in a practical tool.

Run an example from the repository root:

```bash
uv run examples/01_first_command.py
```

Every terminal example includes commands to try in its opening docstring. The
headless example accepts commands after its filename. Start with:

```bash
uv run examples/05_automatic_cli.py --help
uv run examples/05_automatic_cli.py -c "add 12 30"
uv run examples/05_automatic_cli.py --file examples/commands.txt
```
