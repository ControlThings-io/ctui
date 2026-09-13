# ctui examples

Each example introduces only a small part of the library. Read and run them in
this order:

1. `01_first_command.py` — create your first class-based `@command`.
2. `02_class_application.py` — organize commands in a `CtuiApp` subclass.
3. `03_types_and_options.py` — parse types, defaults, and constrained values.
4. `04_named_arguments.py` — explicitly declare Linux-style short and long
   named arguments.
5. `05_hex_bytes.py` — convert familiar hexadecimal formats into immutable
   bytes using a command annotation.
6. `06_fuzzy_patterns.py` — lazily expand finite byte and string patterns or
   sample them without constructing every possibility.
7. `07_automatic_cli.py` — use the automatic CLI shared by every `CtuiApp`.
8. `08_completion_and_validation.py` — create safe dropdown suggestions.
9. `09_async_and_events.py` — run overlapping async commands and show immediate
   started/completed messages.
10. `10_statusbar_progress.py` — track several active commands in the status bar
   and remove each one when it finishes.
11. `11_keyboard_shortcuts.py` — register an application-wide shortcut.
12. `12_custom_layout.py` — compose a layout from reusable widgets.
13. `13_lifecycle_and_storage.py` — persist projects, configs, and records.
14. `filesystem.py` — combine several features in a practical tool.

Run an example from the repository root:

```bash
uv run examples/01_first_command.py
```

Every terminal example includes commands to try in its opening docstring. The
headless example accepts commands after its filename. Start with:

```bash
uv run examples/07_automatic_cli.py --help
uv run examples/07_automatic_cli.py -c "add 12 30"
uv run examples/07_automatic_cli.py --file examples/commands.txt
```
