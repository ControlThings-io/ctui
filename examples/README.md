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
6. `06_automatic_cli.py` — use the automatic CLI shared by every `CtuiApp`.
7. `07_completion_and_validation.py` — create safe dropdown suggestions.
8. `08_async_and_events.py` — run overlapping async commands and show immediate
   started/completed messages.
9. `09_statusbar_progress.py` — track several active commands in the status bar
   and remove each one when it finishes.
10. `10_keyboard_shortcuts.py` — register an application-wide shortcut.
11. `11_custom_layout.py` — compose a layout from reusable widgets.
12. `12_lifecycle_and_storage.py` — persist projects, configs, and records.
13. `filesystem.py` — combine several features in a practical tool.

Run an example from the repository root:

```bash
uv run examples/01_first_command.py
```

Every terminal example includes commands to try in its opening docstring. The
headless example accepts commands after its filename. Start with:

```bash
uv run examples/06_automatic_cli.py --help
uv run examples/06_automatic_cli.py -c "add 12 30"
uv run examples/06_automatic_cli.py --file examples/commands.txt
```
