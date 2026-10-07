"""Embedded terminal/browser dialogs with typed results and synchronous validation.

Dialog classes expose a future resolved by their buttons. Await show_dialog()
inside a running prompt-toolkit application, or use convenience wrappers that
schedule a task and return it. Read-only message and confirmation dialogs keep
buttons focused while scrolling; text-input dialogs focus their editable field.
These developer utilities are retained independently of generated command help.

# Copyright (C) 2019  Justin Searle
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details at <http://www.gnu.org/licenses/>.
"""

from asyncio import Future, Lock, ensure_future
from dataclasses import dataclass
from math import isfinite
from typing import Any, Callable, Mapping, Sequence
from weakref import WeakKeyDictionary

from prompt_toolkit.application.current import get_app
from prompt_toolkit.formatted_text import to_formatted_text
from prompt_toolkit.formatted_text.utils import fragment_list_to_text
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import Float, HSplit, VSplit, Window
from prompt_toolkit.layout.dimension import AnyDimension, D, to_dimension
from prompt_toolkit.layout.scrollable_pane import ScrollablePane
from prompt_toolkit.utils import get_cwidth
from prompt_toolkit.widgets import (
    Checkbox,
    CheckboxList,
    Dialog,
    Label,
    RadioList,
    TextArea,
)

from .base import Button

_dialog_locks = WeakKeyDictionary()
Validator = Callable[[Any], bool | str | None]


class DialogValidationError(ValueError):
    """Expected validation failure; field identifies the input to focus, if any."""

    def __init__(self, message: str, field: str | None = None):
        super().__init__(message)
        self.field = field


def _resolve(future, value):
    if not future.done():
        future.set_result(value)


def _validate(validator: Validator | None, value: Any, field=None):
    """Run a synchronous validator on a converted value without swallowing bugs."""
    if validator is None:
        return
    result = validator(value)
    if result is False or isinstance(result, str):
        raise DialogValidationError(result or "Invalid value", field)
    if result is not None and result is not True:
        raise TypeError(
            "Dialog validators must return True, None, False, or an error string"
        )


def _escape(dialog, handler):
    """Wrap a nonmodal upstream Dialog with ctui's modal Escape scope.

    Upstream retains Tab/arrow handling; the outer public HSplit owns modality
    so its Escape binding also applies to the inner frame and buttons.
    """
    bindings = KeyBindings()

    @bindings.add("escape", eager=True)
    def cancel(event):
        handler()

    dialog.container = HSplit([dialog.container], key_bindings=bindings, modal=True)


def _text_width(text, scrollbar):
    """Allow space for the scrollbar and the buffer's trailing cursor cell."""
    plain = fragment_list_to_text(to_formatted_text(text))
    longest = max((get_cwidth(line) for line in plain.splitlines()), default=0)
    return D(preferred=longest + 1 + int(bool(scrollbar)))


def _scroll_buttons(text_area, buttons):
    """Scroll read-only text without moving focus away from dialog buttons."""
    # Load scrolling helpers only when constructing a dialog.
    from .functions import (
        scroll_line_down,
        scroll_line_up,
        scroll_page_down,
        scroll_page_up,
    )

    for button in buttons:
        for key, handler in (
            ("up", scroll_line_up),
            ("down", scroll_line_down),
            ("pageup", scroll_page_up),
            ("pagedown", scroll_page_down),
        ):

            def scroll(event, handler=handler):
                """Scroll this dialog text using the handler captured for the bound key."""
                handler(event, text_area)

            button.control.key_bindings.add(key)(scroll)


class YesNoDialog:
    """Modal confirmation resolving future to True for Yes or False for No.

    Read-only text never takes focus. Up/Down and Page Up/Page Down scroll while
    buttons retain focus; Enter activates the selected button. Tab and Left/Right
    use the dialog's button navigation. This class builds the dialog but does
    not display it; await show_dialog(instance).
    """

    def __init__(
        self,
        title="",
        text="",
        yes_text="Yes",
        no_text="No",
        width=None,
        wrap_lines=True,
        scrollbar=False,
    ):
        """Construct a confirmation dialog and its result future."""
        self.future = Future()
        self._web_dialog = (title, text, [yes_text, no_text], None)

        def yes_handler():
            """Resolve the dialog with an affirmative result."""
            _resolve(self.future, True)

        def no_handler():
            """Resolve the dialog with a negative result."""
            _resolve(self.future, False)

        self.text_area = TextArea(
            text=text,
            read_only=True,
            # focus_on_click = True,
            focusable=False,
            width=_text_width(text, scrollbar),
            wrap_lines=wrap_lines,
            scrollbar=scrollbar,
        )

        buttons = [
            Button(text=yes_text, width=1, handler=yes_handler),
            Button(text=no_text, width=1, handler=no_handler),
        ]
        _scroll_buttons(self.text_area, buttons)
        self.dialog = Dialog(
            title=title,
            body=self.text_area,
            buttons=buttons,
            with_background=True,
            modal=False,
            width=width,
        )
        _escape(self.dialog, no_handler)

    def __pt_container__(self):
        """Expose the underlying dialog to prompt-toolkit."""
        return self.dialog


class TextInputDialog:
    """Modal text entry resolving future to the entered str or None on Cancel.

    text labels the prompt; it is not an initial input value. The input accepts
    a completer and optional password masking. Enter in the input moves focus
    to Ok and clears completion state; confirmation then resolves the future.
    default supplies initial text. validator receives the entered string and returns
    True/None to accept, False or an error string to reject without closing.
    Construct in an event-loop context and display with show_dialog().
    """

    def __init__(
        self,
        title="",
        text="",
        ok_text="Ok",
        cancel_text="Cancel",
        completer=None,
        password=False,
        width=None,
        default="",
        validator=None,
    ):
        """Construct a text-input dialog and its result future."""
        self.future = Future()
        self.validator = validator
        self.error = Label("")
        self._web_dialog = (
            title,
            text,
            [ok_text, cancel_text],
            {"password": password, "default": default},
        )

        def accept_text(buf):
            """Move focus to confirmation after accepting the input buffer."""
            get_app().layout.focus(ok_button)
            buf.complete_state = None
            return True

        def accept():
            """Resolve the dialog with the entered text."""
            try:
                value = self._web_result({"button": 0, "text": self.text_area.text})
            except DialogValidationError as exc:
                self.error.text = str(exc)
                get_app().layout.focus(self.text_area)
                return
            except Exception as exc:
                if not self.future.done():
                    self.future.set_exception(exc)
                return
            _resolve(self.future, value)

        def cancel():
            """Resolve the dialog with ``None`` to indicate cancellation."""
            _resolve(self.future, None)

        text_width = len(max(text.split("\n"), key=len)) + 2

        self.text_area = TextArea(
            text=default,
            completer=completer,
            multiline=False,
            width=D(preferred=text_width),
            accept_handler=accept_text,
            password=password,
        )

        ok_button = Button(text=ok_text, handler=accept)
        cancel_button = Button(text=cancel_text, handler=cancel)

        self.dialog = Dialog(
            title=title,
            body=HSplit([Label(text=text), self.text_area, self.error]),
            buttons=[ok_button, cancel_button],
            width=width,
            modal=False,
        )
        _escape(self.dialog, cancel)

    def __pt_container__(self):
        """Expose the underlying dialog to prompt-toolkit."""
        return self.dialog

    def _web_result(self, answer):
        if answer["button"] != 0:
            return None
        value = answer.get("text", "")
        _validate(self.validator, value)
        return value


class MessageDialog:
    """Read-only message resolving future to None after acknowledgement.

    By default Ok keeps focus, so Enter closes immediately and arrow/page keys
    scroll the text without a focus switch. focusable=True permits text focus
    when an application explicitly wants it. scrollbar=None chooses visibility
    from content and terminal height at construction; False and True override
    that choice. Width calculation includes wide characters, the scrollbar,
    and the buffer's trailing cursor cell to avoid unnecessary wrapping.
    """

    def __init__(
        self,
        title="",
        text="",
        ok_text="Ok",
        lexer=None,
        width=None,
        wrap_lines=True,
        scrollbar=False,
        focusable=False,
    ):
        """Construct a message dialog sized to its content."""
        self.future = Future()
        self.text = text
        self._web_dialog = (title, text, [ok_text], None)

        def set_done():
            """Resolve the dialog result after acknowledgement."""
            _resolve(self.future, None)

        def dynamic_vertical_scrollbar():
            """Enable scrolling when content exceeds the terminal height."""
            text_fragments = to_formatted_text(self.text)
            text = fragment_list_to_text(text_fragments)
            if text:
                text_height = len(text.splitlines())
                from ctui.web import web_client

                if web_client.get() is not None:
                    return True
                max_text_height = get_app().renderer.output.get_size().rows - 6
                if text_height > max_text_height:
                    return True
            return False

        scrollbar = dynamic_vertical_scrollbar() if scrollbar is None else scrollbar
        self.text_area = TextArea(
            text=text,
            lexer=lexer,
            read_only=True,
            focusable=focusable,
            width=_text_width(text, scrollbar),
            wrap_lines=wrap_lines,
            scrollbar=scrollbar,
        )

        ok_button = Button(text=ok_text, handler=set_done)
        _scroll_buttons(self.text_area, [ok_button])

        self.dialog = Dialog(
            title=title,
            body=self.text_area,
            buttons=[ok_button],
            width=width,
            modal=False,
        )
        _escape(self.dialog, set_done)

    def __pt_container__(self):
        """Expose the underlying dialog to prompt-toolkit."""
        return self.dialog


async def show_dialog(dialog) -> Any:
    """Insert a modal float, await its result, then restore prior focus.

    In web mode, route to the browser view that initiated the command/callback.
    Otherwise require a running prompt-toolkit app whose root exposes floats.
    Dialogs are single-use and queued per application (per view in web mode).
    The dialog must provide a future and a prompt-toolkit container. Always
    remove the float and restore focus on completion or cancellation. Request
    redraws explicitly: callers may resume after asynchronous work, after the
    input event's redraw has already finished.
    """
    from ctui.web import web_client

    client = web_client.get()
    if client is not None:
        return await client.show_dialog(dialog)
    app = get_app()
    lock = _dialog_locks.setdefault(app, Lock())
    try:
        async with lock:
            float_ = Float(content=dialog)
            floats = app.layout.container.floats
            focused_before = app.layout.current_window
            floats.insert(0, float_)
            try:
                app.layout.focus(dialog)
                app.invalidate()
                return await dialog.future
            finally:
                if float_ in floats:
                    floats.remove(float_)
                if focused_before in list(app.layout.find_all_windows()):
                    app.layout.focus(focused_before)
                else:
                    app.layout.focus_next()
                app.invalidate()
    except BaseException:
        dialog.future.cancel()
        raise


# Functions that use dialog classes and return results


def _schedule(coroutine):
    """Track convenience dialogs in the running frontend for shutdown cleanup."""
    from ctui.web import web_client

    client = web_client.get()
    if client is not None:
        return client.session.create_background_task(coroutine)
    app = get_app()
    if app.is_running:
        return app.create_background_task(coroutine)
    return ensure_future(coroutine)


def func_pass():
    """Provide a no-operation default dialog callback."""


def yes_no_dialog(
    title="",
    text="",
    yes_text="Yes",
    yes_func=func_pass,
    no_text="No",
    no_func=func_pass,
):
    """Schedule a Yes/No dialog and return its asyncio task.

    After approval call yes_func(), otherwise no_func(). Callbacks take no
    arguments and are synchronous; their return values are ignored. Await the
    returned task to observe completion or callback errors. For an awaitable
    boolean result instead, use show_dialog(YesNoDialog(...)).
    """

    async def coroutine():
        """Show the confirmation and invoke the selected callback."""
        dialog = YesNoDialog(title=title, text=text, yes_text=yes_text, no_text=no_text)
        result = await show_dialog(dialog)
        if result is True:
            yes_func()
        else:
            no_func()

    return _schedule(coroutine())


def input_dialog(
    title="",
    text="",
    ok_text="OK",
    cancel_text="Cancel",
    completer=None,
    password=False,
    default="",
    validator=None,
):
    """Schedule text entry and return a task yielding str or None on Cancel.

    text is a prompt label, completer supplies input suggestions, and password
    masks entry. Requires the active application's modal float support, just
    like show_dialog().
    """

    async def coroutine():
        """Show the input dialog and return its result."""
        open_dialog = TextInputDialog(
            title=title,
            text=text,
            ok_text=ok_text,
            cancel_text=cancel_text,
            completer=completer,
            password=password,
            default=default,
            validator=validator,
        )
        return await show_dialog(open_dialog)

    return _schedule(coroutine())


def message_dialog(
    title="",
    text="",
    ok_text="Ok",
    lexer=None,
    width=None,
    wrap_lines=True,
    scrollbar=None,
):
    """Schedule a message dialog and return a task yielding None on acknowledgement.

    The call itself does not wait; await the returned task when sequencing
    matters. scrollbar=None selects based on terminal height at construction.
    Ok retains focus during scrolling, so Enter acknowledges immediately.
    """

    async def coroutine():
        """Show the message dialog until it is acknowledged."""
        dialog = MessageDialog(
            title=title,
            text=text,
            ok_text=ok_text,
            lexer=lexer,
            width=width,
            wrap_lines=wrap_lines,
            scrollbar=scrollbar,
        )
        await show_dialog(dialog)

    return _schedule(coroutine())


@dataclass(frozen=True)
class DictField:
    """Optional dictionary field label, help, scalar type override and validator.

    value_type must be str, int, float or bool. It is required for an initial
    None; otherwise infer the exact type of the initial value. Validators receive
    converted values and return True/None to accept, False or an error string to
    reject. Exceptions from validators propagate as application errors.
    """

    label: str | None = None
    help: str = ""
    value_type: type | None = None
    validator: Validator | None = None


class _ValueDialog:
    """Shared embedded selection/form validation and cancellation mechanics."""

    def _build(self, title, text, body, buttons, width=None):
        self.future = Future()
        self.error = Label("")
        self.dialog = Dialog(
            title=title,
            body=HSplit([Label(text), body, self.error]),
            buttons=buttons,
            width=width,
            modal=False,
        )
        _escape(self.dialog, lambda: self._finish(None))

    def _finish(self, value):
        _resolve(self.future, value)

    def _accept(self, answer):
        try:
            value = self._web_result(answer)
        except DialogValidationError as exc:
            self.error.text = str(exc)
            inputs = getattr(self, "inputs", {})
            control = inputs.get(exc.field) or next(iter(inputs.values()), None)
            if control is None and getattr(self, "values", None):
                control = getattr(self, "list", None)
            if control is not None:
                get_app().layout.focus(control)
            get_app().invalidate()
            return
        except Exception as exc:
            if not self.future.done():
                self.future.set_exception(exc)
            return
        self.error.text = ""
        self._finish(value)

    def __pt_container__(self):
        return self.dialog


class ButtonDialog(_ValueDialog):
    """Choose a value from (label, value) buttons; Escape returns None.

    Supply at least one button. Values may be arbitrary objects except None,
    which is reserved for cancellation. There is no implicit Cancel button.
    Construct inside an event loop and await show_dialog(instance) to display.
    """

    def __init__(
        self,
        title: str = "",
        text: str = "",
        buttons: Sequence[tuple[str, Any]] = (),
        *,
        width: AnyDimension = None,
    ):
        self.values = list(buttons)
        if not self.values or any(value is None for _, value in self.values):
            raise ValueError("Supply buttons with non-None values")
        self._web_dialog = (title, text, [label for label, _ in self.values], None)
        self._web_cancel = -1
        self._build(
            title,
            text,
            Label(""),
            [
                Button(label, handler=lambda i=i: self._accept({"button": i}))
                for i, (label, _) in enumerate(self.values)
            ],
            width,
        )

    def _web_result(self, answer):
        index = answer["button"]
        return None if index == -1 else self.values[index][1]


class RadioListDialog(_ValueDialog):
    """Select one (value, label) entry, returning its value or None on Cancel.

    Values must be unique and non-None. default selects a value; without it the
    first entry is selected. validator receives the selected value. Arrow keys
    move through the upstream list; Space selects, Tab moves to Ok/Cancel.
    """

    def __init__(
        self,
        title: str = "",
        text: str = "",
        values: Sequence[tuple[Any, str]] = (),
        *,
        default: Any = None,
        ok_text: str = "Ok",
        cancel_text: str = "Cancel",
        validator: Validator | None = None,
        width: AnyDimension = None,
    ):
        self.values = list(values)
        _choices(self.values)
        if default is not None and default not in [value for value, _ in self.values]:
            raise ValueError("Unknown default value")
        self.validator = validator
        self.list = RadioList(self.values, default=default)
        self._web_dialog = (title, text, [ok_text, cancel_text], None)
        self._web_options = {
            "choices": [
                fragment_list_to_text(to_formatted_text(label))
                for _, label in self.values
            ],
            "multiple": False,
            "selected": [
                next(
                    i
                    for i, (value, _) in enumerate(self.values)
                    if value == self.list.current_value
                )
            ],
        }
        self._build(
            title,
            text,
            self.list,
            [
                Button(ok_text, handler=self._accept_selected),
                Button(cancel_text, handler=lambda: self._finish(None)),
            ],
            width,
        )

    def _accept_selected(self):
        selected = next(
            i
            for i, (value, _) in enumerate(self.values)
            if value == self.list.current_value
        )
        self._accept({"button": 0, "selected": [selected]})

    def _web_result(self, answer):
        if answer["button"] != 0:
            return None
        indices = _indices(answer, len(self.values))
        if len(indices) != 1:
            raise DialogValidationError("Select one item")
        value = self.values[indices[0]][0]
        _validate(self.validator, value)
        return value


class CheckboxListDialog(_ValueDialog):
    """Select (value, label) entries, returning a list or None on Cancel.

    Values must be unique and non-None; default_values preselects entries. An
    accepted empty selection is []. Results follow the supplied entry order.
    validator receives the selected list; keyboard navigation follows upstream.
    """

    def __init__(
        self,
        title: str = "",
        text: str = "",
        values: Sequence[tuple[Any, str]] = (),
        *,
        default_values: Sequence[Any] = (),
        ok_text: str = "Ok",
        cancel_text: str = "Cancel",
        validator: Validator | None = None,
        width: AnyDimension = None,
    ):
        self.values = list(values)
        _choices(self.values, allow_empty=True)
        defaults = list(default_values)
        if any(v not in [value for value, _ in self.values] for v in defaults):
            raise ValueError("Unknown default value")
        self.validator = validator
        self.list = (
            CheckboxList(self.values, default_values=defaults)
            if self.values
            else Label("No items")
        )
        self._web_dialog = (title, text, [ok_text, cancel_text], None)
        self._web_options = {
            "choices": [
                fragment_list_to_text(to_formatted_text(label))
                for _, label in self.values
            ],
            "multiple": True,
            "selected": [
                i for i, (value, _) in enumerate(self.values) if value in defaults
            ],
        }
        self._build(
            title,
            text,
            self.list,
            [
                Button(ok_text, handler=self._accept_selected),
                Button(cancel_text, handler=lambda: self._finish(None)),
            ],
            width,
        )

    def _accept_selected(self):
        selected = (
            [
                i
                for i, (value, _) in enumerate(self.values)
                if value in self.list.current_values
            ]
            if self.values
            else []
        )
        self._accept({"button": 0, "selected": selected})

    def _web_result(self, answer):
        if answer["button"] != 0:
            return None
        indices = _indices(answer, len(self.values))
        value = [v for i, (v, _) in enumerate(self.values) if i in indices]
        _validate(self.validator, value)
        return value


def _choices(values, allow_empty=False):
    if not values and not allow_empty:
        raise ValueError("Supply at least one choice")
    seen = []
    for value, _ in values:
        if value is None or value in seen:
            raise ValueError("Choice values must be unique and non-None")
        seen.append(value)


def _indices(answer, count):
    indices = answer.get("selected", [])
    if (
        not isinstance(indices, list)
        or any(type(i) is not int or not 0 <= i < count for i in indices)
        or len(set(indices)) != len(indices)
    ):
        raise DialogValidationError("Invalid selection")
    return indices


class DictInputDialog(_ValueDialog):
    """Edit fixed string keys, returning a new typed dict or None on Cancel.

    Copy values at construction and preserve key order; never mutate the input.
    Only str/int/finite float/bool values are supported. fields maps existing
    keys to DictField metadata, including explicit types for initial None values.
    Labels and editable values share aligned rows separated by a divider; help
    sits below its value. Booleans use checkboxes; other types use bracketed text
    entry with distinct focus styling. Empty strings are valid;
    numeric fields require values. Field validators run after conversion; the
    optional whole-dictionary validator then checks a separate copy. Rejected
    input stays open, retains edits and focuses the first invalid field. Values
    are collected only: callers own subsequent application/persistence changes.
    """

    def __init__(
        self,
        title: str = "",
        text: str = "",
        values: Mapping[str, str | int | float | bool | None] | None = None,
        *,
        fields: Mapping[str, DictField] | None = None,
        ok_text: str = "Ok",
        cancel_text: str = "Cancel",
        validator: Validator | None = None,
        width: AnyDimension = None,
    ):
        self.values = dict(values or {})
        self.fields = dict(fields or {})
        if any(not isinstance(key, str) for key in self.values):
            raise TypeError("Dictionary keys must be strings")
        if self.fields.keys() - self.values.keys():
            raise ValueError("Field metadata must reference existing keys")
        self.validator = validator
        self.inputs = {}
        self.types = {}
        descriptions = []
        labels = {key: self.fields.get(key, DictField()).label for key in self.values}
        labels = {
            key: label if label is not None else key for key, label in labels.items()
        }
        label_width = max(
            [get_cwidth("Field")] + [get_cwidth(label) for label in labels.values()]
        )

        def label_dimension():
            # Fixed across rows; reserve space for editors on narrow terminals.
            columns = get_app().output.get_size().columns
            requested = to_dimension(width).preferred if width is not None else columns
            available = min(columns, requested or columns)
            return D.exact(min(label_width, max(1, available // 3)))

        def row(label, value):
            return VSplit(
                [
                    Label(label, width=label_dimension, style="class:dict-label"),
                    Label(" │ ", width=3, style="class:dict-divider"),
                    value,
                ]
            )

        body = [
            row("Field", Label("Value (editable)", style="class:dict-label")),
            VSplit(
                [
                    Window(
                        height=1,
                        char="─",
                        width=label_dimension,
                        style="class:dict-divider",
                    ),
                    Label("─┼─", width=3, style="class:dict-divider"),
                    Window(height=1, char="─", style="class:dict-divider"),
                ]
            ),
        ]
        for key, value in self.values.items():
            field = self.fields.get(key, DictField())
            value_type = field.value_type or type(value)
            if value_type not in (str, int, float, bool):
                raise TypeError(
                    f"Unsupported type for {key}; supply a scalar value_type for None"
                )
            if value_type is bool and value is not None and type(value) is not bool:
                raise TypeError(f"Boolean field {key} requires bool or None")
            if value is not None and type(value) not in (str, int, float, bool):
                raise TypeError(f"Unsupported value for {key}")
            self.types[key] = value_type
            label = labels[key]
            initial = (
                bool(value)
                if value_type is bool
                else "" if value is None else str(value)
            )

            def value_style(key=key):
                focused = get_app().layout.has_focus(self.inputs[key])
                return "class:dict-value" + (
                    " class:dict-value.focused" if focused else ""
                )

            control = (
                Checkbox("", checked=initial)
                if value_type is bool
                else TextArea(text=initial, multiline=False)
            )
            self.inputs[key] = control

            if value_type is bool:
                editor = VSplit([control], style=value_style)
            else:
                # TextArea accepts a static style; its public Window accepts a callable.
                control.window.style = (
                    lambda value_style=value_style: "class:text-area " + value_style()
                )
                editor = VSplit(
                    [
                        Label("[", width=1),
                        control,
                        Label("]", width=1),
                    ],
                    style=value_style,
                    width=D(min=12),
                )
            body.append(row(label, editor))
            if field.help:
                body.append(row("", Label(" " + field.help, style="class:dict-help")))
            descriptions.append(
                {
                    "key": key,
                    "label": label,
                    "help": field.help,
                    "boolean": value_type is bool,
                    "value": initial,
                }
            )
        self._web_dialog = (title, text, [ok_text, cancel_text], None)
        self._web_options = {"fields": descriptions}
        self._build(
            title,
            text,
            ScrollablePane(
                HSplit(body if self.values else [Label("No fields")]),
                show_scrollbar=True,
            ),
            [
                Button(ok_text, handler=self._accept_values),
                Button(cancel_text, handler=lambda: self._finish(None)),
            ],
            width,
        )

    def _accept_values(self):
        values = {
            key: control.checked if self.types[key] is bool else control.text
            for key, control in self.inputs.items()
        }
        self._accept({"button": 0, "values": values})

    def _web_result(self, answer):
        if answer["button"] != 0:
            return None
        raw = answer.get("values")
        if not isinstance(raw, dict) or raw.keys() != self.values.keys():
            raise DialogValidationError("Invalid dictionary fields")
        result = {}
        for key in self.values:
            value_type = self.types[key]
            value = raw[key]
            if value_type is bool:
                if type(value) is not bool:
                    raise DialogValidationError("Expected a checkbox value", key)
            else:
                if not isinstance(value, str):
                    raise DialogValidationError("Expected text", key)
                try:
                    value = value_type(value)
                    if value_type is float and not isfinite(value):
                        raise ValueError
                except (ValueError, OverflowError):
                    raise DialogValidationError(
                        f"{key}: enter a valid {value_type.__name__}", key
                    ) from None
            _validate(self.fields.get(key, DictField()).validator, value, key)
            result[key] = value
        _validate(self.validator, dict(result))
        return result


def button_dialog(
    title: str = "",
    text: str = "",
    buttons: Sequence[tuple[str, Any]] = (),
    *,
    width: AnyDimension = None,
):
    """Schedule ButtonDialog; await the returned task for its value or None."""
    return _schedule(show_dialog(ButtonDialog(title, text, buttons, width=width)))


def radiolist_dialog(
    title: str = "",
    text: str = "",
    values: Sequence[tuple[Any, str]] = (),
    *,
    default: Any = None,
    ok_text: str = "Ok",
    cancel_text: str = "Cancel",
    validator: Validator | None = None,
    width: AnyDimension = None,
):
    """Schedule RadioListDialog; await the returned task for its value or None."""
    return _schedule(
        show_dialog(
            RadioListDialog(
                title,
                text,
                values,
                default=default,
                ok_text=ok_text,
                cancel_text=cancel_text,
                validator=validator,
                width=width,
            )
        )
    )


def checkboxlist_dialog(
    title: str = "",
    text: str = "",
    values: Sequence[tuple[Any, str]] = (),
    *,
    default_values: Sequence[Any] = (),
    ok_text: str = "Ok",
    cancel_text: str = "Cancel",
    validator: Validator | None = None,
    width: AnyDimension = None,
):
    """Schedule CheckboxListDialog; await the returned task for its list or None."""
    return _schedule(
        show_dialog(
            CheckboxListDialog(
                title,
                text,
                values,
                default_values=default_values,
                ok_text=ok_text,
                cancel_text=cancel_text,
                validator=validator,
                width=width,
            )
        )
    )


def dict_input_dialog(
    title: str = "",
    text: str = "",
    values: Mapping[str, str | int | float | bool | None] | None = None,
    *,
    fields: Mapping[str, DictField] | None = None,
    ok_text: str = "Ok",
    cancel_text: str = "Cancel",
    validator: Validator | None = None,
    width: AnyDimension = None,
):
    """Schedule DictInputDialog; await the returned task for a new dict or None."""
    return _schedule(
        show_dialog(
            DictInputDialog(
                title,
                text,
                values,
                fields=fields,
                ok_text=ok_text,
                cancel_text=cancel_text,
                validator=validator,
                width=width,
            )
        )
    )
