from __future__ import annotations

from datetime import datetime
from pathlib import Path

from llmm import console, llm_client
from llmm.config import Config
from llmm.dialog import Dialog, DialogWriter, Message, RollbackError


def run(config: Config, dialog: Dialog, dialogs_dir: Path) -> None:
    """Start the interactive chat REPL.

    Reads user input from stdin. User messages and /commands share the same prompt.
    Writes dialog turns to a .dlg.toml file in *dialogs_dir*.
    """
    writer = DialogWriter()
    _print_task(dialog)

    while True:
        try:
            user_input = input("> ")
        except (EOFError, KeyboardInterrupt):
            print()
            _cmd_exit(writer)
            return

        user_input = user_input.strip()
        if not user_input:
            continue

        if user_input.startswith("/"):
            cmd = user_input.split()[0].lower()
            if cmd == "/exit":
                _cmd_exit(writer)
                return
            elif cmd == "/new":
                _cmd_new(writer, dialog)
                _print_task(dialog)
            elif cmd == "/back":
                _cmd_back(writer, dialog)
            elif cmd == "/history":
                _cmd_history(dialog)
            else:
                console.print_info(f"Unknown command: {cmd}")
        else:
            _handle_message(user_input, writer, dialog, config, dialogs_dir)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def _cmd_exit(writer: DialogWriter) -> None:
    if writer.is_open:
        path = writer.path
        writer.close()
        console.print_info(f"Dialog file closed: {path}")


def _cmd_new(writer: DialogWriter, dialog: Dialog) -> None:
    if writer.is_open:
        path = writer.path
        writer.close()
        console.print_info(f"Dialog file saved: {path}")
    dialog.messages.clear()
    console.print_info("Dialog cleared.")


def _cmd_back(writer: DialogWriter, dialog: Dialog) -> None:
    try:
        dialog.rollback()
    except RollbackError:
        console.print_info("Nothing to roll back.")
        _print_task(dialog)
        return

    # Rollback succeeded — close the current file so the next message starts a new one
    if writer.is_open:
        path = writer.path
        writer.close()
        console.print_info(f"Dialog file closed: {path}")

    if dialog.messages:
        # Messages always come in (user, assistant) pairs, so [-2]/[-1] are the last pair
        console.print_user(f"{dialog.user_role}: {dialog.messages[-2].content}")
        console.print_llm(f"{dialog.assistant_role}: {dialog.messages[-1].content}")
    else:
        console.print_info("No further rollback is possible.")
        _print_task(dialog)


def _cmd_history(dialog: Dialog) -> None:
    if not dialog.messages:
        console.print_info("(No messages in the current dialog.)")
        return
    for msg in dialog.messages:
        if msg.role == "user":
            console.print_user(f"{dialog.user_role}: {msg.content}")
        else:
            console.print_llm(f"{dialog.assistant_role}: {msg.content}")


# ---------------------------------------------------------------------------
# Message handling
# ---------------------------------------------------------------------------

def _handle_message(
    text: str,
    writer: DialogWriter,
    dialog: Dialog,
    config: Config,
    dialogs_dir: Path,
) -> None:
    # Re-print with role label (the raw input() line has no label)
    console.print_user(f"{dialog.user_role}: {text}")

    # Open a new file on the first message of a dialog
    if not writer.is_open:
        path = _make_dialog_path(dialogs_dir)
        writer.open(path, dialog)
        console.print_info(f"Dialog file opened: {path}")

    user_msg = Message(role="user", content=text)
    writer.append(user_msg)
    dialog.messages.append(user_msg)

    try:
        response = llm_client.complete(
            list(dialog.messages),
            config,
            system_prompt=dialog.system_prompt,
        )
    except Exception as exc:  # noqa: BLE001
        console.print_error(str(exc))
        return

    console.print_llm(f"{dialog.assistant_role}: {response}")

    assistant_msg = Message(role="assistant", content=response)
    writer.append(assistant_msg)
    dialog.messages.append(assistant_msg)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_task(dialog: Dialog) -> None:
    if dialog.task:
        console.print_info(dialog.task)


def _make_dialog_path(dialogs_dir: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return dialogs_dir / f"dialog_{timestamp}.dlg.toml"
