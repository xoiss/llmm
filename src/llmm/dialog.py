from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import tomlkit


@dataclass
class Message:
    role: str
    content: str


class RollbackError(Exception):
    """Raised when there are no message pairs to roll back."""


@dataclass
class Dialog:
    system_prompt: str | None = None
    task: str | None = None
    user_role: str = "user"
    assistant_role: str = "assistant"
    messages: list[Message] = field(default_factory=list)

    def rollback(self) -> None:
        """Remove the last (user, assistant) message pair.

        Raises RollbackError if there is nothing to remove.
        """
        if len(self.messages) < 2:
            raise RollbackError("No message pairs to roll back.")
        self.messages.pop()  # assistant
        self.messages.pop()  # user


class DialogWriter:
    """Manages writing a Dialog to a .dlg.toml file turn by turn."""

    def __init__(self) -> None:
        self._path: Path | None = None

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def is_open(self) -> bool:
        return self._path is not None

    def open(self, path: Path, dialog: Dialog) -> None:
        """Create the dialog file and write the header plus any existing messages."""
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)

        doc = tomlkit.document()

        prompt_table = tomlkit.table()
        if dialog.system_prompt is not None:
            prompt_table.add("system", dialog.system_prompt)
        doc.add("prompt", prompt_table)

        role_names_table = tomlkit.table()
        role_names_table.add("user", dialog.user_role)
        role_names_table.add("assistant", dialog.assistant_role)
        doc.add("role_names", role_names_table)

        chat_table = tomlkit.table()
        if dialog.task is not None:
            chat_table.add("task", dialog.task)
        doc.add("chat", chat_table)

        if dialog.messages:
            messages_aot = tomlkit.aot()
            for msg in dialog.messages:
                item = tomlkit.table()
                item.add("role", msg.role)
                item.add("content", msg.content)
                messages_aot.append(item)
            doc.add("messages", messages_aot)

        path.write_text(tomlkit.dumps(doc), encoding="utf-8")

    def append(self, message: Message) -> None:
        """Append a single message to the open dialog file."""
        if self._path is None:
            raise RuntimeError("DialogWriter is not open.")

        doc = tomlkit.loads(self._path.read_text(encoding="utf-8"))

        item = tomlkit.table()
        item.add("role", message.role)
        item.add("content", message.content)

        if "messages" not in doc:
            doc.add("messages", tomlkit.aot())
        doc["messages"].append(item)

        self._path.write_text(tomlkit.dumps(doc), encoding="utf-8")

    def close(self) -> None:
        """Disassociate the writer from its file (does not delete the file)."""
        self._path = None


def load_dialog(path: Path) -> Dialog:
    """Parse a .dlg.toml file and return a Dialog."""
    data = tomlkit.loads(path.read_text(encoding="utf-8"))

    prompt = data.get("prompt", {})
    system_prompt: str | None = prompt.get("system") or None

    role_names = data.get("role_names", {})
    user_role = str(role_names.get("user", "user"))
    assistant_role = str(role_names.get("assistant", "assistant"))

    chat = data.get("chat", {})
    task: str | None = chat.get("task") or None

    messages = [
        Message(role=m["role"], content=m["content"])
        for m in data.get("messages", [])
    ]

    return Dialog(
        system_prompt=system_prompt,
        task=task,
        user_role=user_role,
        assistant_role=assistant_role,
        messages=messages,
    )
