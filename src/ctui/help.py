"""Shared command reference and interface-specific help guidance."""

import inspect

from ctui.commands import Argument, CommandNotFound


def command_help(app, target):
    """Describe one command level, resolving exact names before prefixes."""
    names = {**app.commands.commands, **app.commands.aliases}
    path = []
    for token in target.split():
        choices = {
            words[len(path)]
            for name in names
            if (words := name.split())[: len(path)] == path and len(words) > len(path)
        }
        matches = sorted(word for word in choices if word.startswith(token))
        if token in choices:
            path.append(token)
        elif len(matches) == 1:
            path.append(matches[0])
        elif matches:
            raise CommandNotFound(
                f"Ambiguous help target {token!r}: {', '.join(matches)}"
            )
        else:
            raise CommandNotFound(f"Unknown help target: {target}")
    name = " ".join(path)
    item = names.get(name)
    if item is not None:
        name = item.name
        path = name.split()
    lines = [f"Help: {name}"] if path else [app.help_message]
    if item is not None:
        lines.extend(["", "Usage: " + item.help])
        documentation = inspect.getdoc(item.func) or ""
        if "\n" in documentation:
            lines.extend(["", documentation.split("\n", 1)[1].strip()])
        if item.aliases:
            lines.extend(["", "Aliases: " + ", ".join(item.aliases)])
        for parameter in item.parameters:
            config = item.arguments.get(parameter.name, Argument())
            annotation = item.hints.get(parameter.name, parameter.annotation)
            type_name = getattr(annotation, "__name__", str(annotation))
            label = ", ".join(config.flags) or parameter.name
            default = (
                "required"
                if parameter.default is inspect.Parameter.empty
                else f"default: {parameter.default!r}"
            )
            lines.append(f"  {label}: {type_name} ({default}) {config.help}".rstrip())
    children = {}
    for command in app.commands:
        words = command.name.split()
        if words[: len(path)] != path or len(words) <= len(path):
            continue
        child = words[len(path)]
        full_name = " ".join(path + [child])
        direct = app.commands.commands.get(full_name)
        children[child] = direct.desc if direct else "Subcommands"
    if children:
        lines.extend(["", "Subcommands:" if path else "Commands:"])
        lines.extend(
            f"  {child:<20} {desc}" for child, desc in sorted(children.items())
        )
    lines.extend(
        [
            "",
            "Use help <command> to see subcommands and argument details.",
            "For nested commands, use help <command> <subcommand>.",
        ]
    )
    return "\n".join(lines)


def ui_guidance(app):
    """Explain the built-in bindings by the window they affect."""
    text = """Input window — type and edit commands here:
  Enter                 Run the command; you can enter another while it runs.
  Tab                   Complete a command or argument.
  Up / Down             Navigate completion choices or input history.
  Left / Right          Move the input cursor.
  Ctrl-A / Ctrl-E       Move to the beginning / end of input.
  Ctrl-U / Ctrl-K       Delete input before / after the cursor.
  Ctrl-W                Delete the preceding word.
  Ctrl-C                Clear input (does not cancel running commands).
  Ctrl-D                Delete the next character; exit if input is empty.
  Quote values containing spaces. Type a space to advance completion.

Output window — these keys work while input keeps focus:
  Home / End            Scroll to the beginning / end of output.
  Page Up / Page Down   Scroll output one page.
  Ctrl-Up / Ctrl-Down   Scroll output one line.
  Ctrl-L                Clear output, preserving input.
  Select and copy output using your terminal's mouse and clipboard shortcuts.
  Use your terminal's paste shortcut to paste into input.

Help dialog:
  Help preserves the main output. Use Up/Down or Page Up/Page Down to scroll.
  Ok stays focused while scrolling; press Enter to close.
  Closing help restores the previous input focus.

Exit:
  exit                  Shut down normally.
  Ctrl-Q                Force the UI to quit."""
    if app.shortcuts:
        text += "\n\nApplication shortcuts (prompt-toolkit key names):"
        for keys, _, description in app.shortcuts:
            text += f"\n  {' '.join(keys):<20} {description or 'Application action'}"
    return text
