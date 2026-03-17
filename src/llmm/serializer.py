from __future__ import annotations

import jinja2

from llmm.dialog import Dialog


def serialize(template: jinja2.Template, dialog: Dialog) -> str:
    """Render *dialog* to a plain-text string using the given Jinja2 *template*.

    Template context variables:
        user_role       -- display name for the user role
        assistant_role  -- display name for the assistant role
        system_prompt   -- system prompt string, or None if absent
        task            -- user task/briefing string, or None if absent
        messages        -- list of {role, content} dicts in conversation order;
                           the ``role`` field contains the display name, not the
                           raw ``"user"``/``"assistant"`` identifier
    """
    messages = [
        {
            "role": dialog.user_role if m.role == "user" else dialog.assistant_role,
            "content": m.content,
        }
        for m in dialog.messages
    ]

    return template.render(
        user_role=dialog.user_role,
        assistant_role=dialog.assistant_role,
        system_prompt=dialog.system_prompt,
        task=dialog.task,
        messages=messages,
    )
