from __future__ import annotations

import argparse
import sys
from pathlib import Path

from llmm import config as config_module
from llmm import console
from llmm import prompt as prompt_module


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="llmm",
        description="Run LLM workflows from the command line.",
    )
    parser.add_argument(
        "-c", "--config",
        metavar="FILE",
        type=Path,
        default=None,
        help="Path to the config file (default: ~/.llmm/config.toml).",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # ---- run ----------------------------------------------------------------
    run_p = subparsers.add_parser(
        "run",
        help="Batch-process one file or a directory (Scenario 1).",
    )
    run_p.add_argument(
        "-p", "--prompt",
        metavar="PROMPT_FILE",
        type=Path,
        default=None,
        help="Prompt file. Defaults to prompt.toml in the input directory.",
    )
    run_input = run_p.add_mutually_exclusive_group()
    run_input.add_argument(
        "-d", "--document",
        metavar="DOCUMENT_FILE",
        type=Path,
        help="Text document (.txt, .md) to process.",
    )
    run_input.add_argument(
        "-i", "--image",
        metavar="IMAGE_FILE",
        type=Path,
        help="Image file (.png, .jpg) to process.",
    )
    run_p.add_argument(
        "-o", "--output",
        metavar="OUTPUT_FILE",
        type=Path,
        default=None,
        help="Output file path (stdout if omitted).",
    )
    run_p.add_argument(
        "-I", "--input-dir",
        metavar="INPUT_DIR",
        type=Path,
        default=None,
        help="Process all supported files in this directory.",
    )
    run_p.add_argument(
        "-O", "--output-dir",
        metavar="OUTPUT_DIR",
        type=Path,
        default=None,
        help="Directory for output files (defaults to INPUT_DIR).",
    )

    # ---- chat ---------------------------------------------------------------
    chat_p = subparsers.add_parser(
        "chat",
        help="Start an interactive dialog session (Scenario 2).",
    )
    chat_p.add_argument(
        "-p", "--prompt",
        metavar="PROMPT_FILE",
        type=Path,
        default=None,
        help="Prompt file. Defaults to prompt.toml in DIALOGS_DIR.",
    )
    chat_p.add_argument(
        "-D", "--dialogs-dir",
        metavar="DIALOGS_DIR",
        type=Path,
        default=None,
        help="Directory where dialog files are saved (default: current directory).",
    )

    # ---- export -------------------------------------------------------------
    export_p = subparsers.add_parser(
        "export",
        help="Serialize dialog file(s) to plain text.",
    )
    export_p.add_argument(
        "-t", "--template",
        metavar="TEMPLATE_FILE",
        type=Path,
        default=None,
        help="Jinja2 template file. Defaults to template.jinja in the dialog directory.",
    )
    export_p.add_argument(
        "-d", "--dialog",
        metavar="DIALOG_FILE",
        type=Path,
        default=None,
        help="Input .dlg.toml file (stdin if omitted).",
    )
    export_p.add_argument(
        "-s", "--serialized",
        metavar="SERIALIZED_FILE",
        type=Path,
        default=None,
        help="Output .dlg.md file (stdout if omitted).",
    )
    export_p.add_argument(
        "-D", "--dialogs-dir",
        metavar="DIALOGS_DIR",
        type=Path,
        default=None,
        help="Directory to search for *.dlg.toml files.",
    )
    export_p.add_argument(
        "-S", "--serialized-dir",
        metavar="SERIALIZED_DIR",
        type=Path,
        default=None,
        help="Directory for serialized .dlg.md files (defaults to DIALOGS_DIR).",
    )

    args = parser.parse_args()
    cfg = config_module.load_config(args.config)

    if args.command == "run":
        _cmd_run(args, cfg)
    elif args.command == "chat":
        _cmd_chat(args, cfg)
    elif args.command == "export":
        _cmd_export(args, cfg)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_prompt(
    prompt_arg: Path | None,
    lookup_dir: Path,
) -> Path | None:
    if prompt_arg is not None:
        return prompt_arg
    candidate = lookup_dir / "prompt.toml"
    return candidate if candidate.exists() else None


def _require_prompt(
    prompt_arg: Path | None,
    lookup_dir: Path,
) -> prompt_module.ParsedPrompt:
    path = _resolve_prompt(prompt_arg, lookup_dir)
    if path is None:
        console.print_error(
            f"Prompt file 'prompt.toml' not found in {lookup_dir}. "
            "Specify a path with --prompt."
        )
        sys.exit(1)
    return prompt_module.parse_prompt(path)


def _resolve_template(
    template_arg: Path | None,
    lookup_dir: Path,
) -> Path | None:
    if template_arg is not None:
        return template_arg
    candidate = lookup_dir / "template.jinja"
    return candidate if candidate.exists() else None


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------

def _cmd_run(args: argparse.Namespace, cfg: config_module.Config) -> None:
    from llmm import scenario1

    if args.input_dir is not None:
        # ---- Directory mode -------------------------------------------------
        input_dir: Path = args.input_dir
        parsed = _require_prompt(args.prompt, input_dir)
        effective_cfg = prompt_module.apply_overrides(cfg, parsed.config_overrides)

        supported = (
            prompt_module.SUPPORTED_TEXT_EXTENSIONS
            | prompt_module.SUPPORTED_IMAGE_EXTENSIONS
        )
        input_files = sorted(
            f for f in input_dir.iterdir()
            if f.is_file() and f.suffix.lower() in supported
        )

        if not input_files:
            console.print_info(f"No supported input files found in {input_dir}.")
            return

        out_dir = args.output_dir if args.output_dir is not None else input_dir
        output_files: list[Path | None] = [
            out_dir / (f.stem + ".out.md") for f in input_files
        ]
        scenario1.run(effective_cfg, parsed, input_files, output_files)

    else:
        # ---- Single-file or stdin mode --------------------------------------
        if args.document is not None:
            lookup_dir = args.document.parent
        elif args.image is not None:
            lookup_dir = args.image.parent
        else:
            lookup_dir = Path.cwd()

        parsed = _require_prompt(args.prompt, lookup_dir)
        effective_cfg = prompt_module.apply_overrides(cfg, parsed.config_overrides)

        if args.document is not None:
            scenario1.run(effective_cfg, parsed, [args.document], [args.output])
        elif args.image is not None:
            scenario1.run(effective_cfg, parsed, [args.image], [args.output])
        else:
            _run_stdin(effective_cfg, parsed, args.output)


def _run_stdin(
    cfg: config_module.Config,
    parsed: prompt_module.ParsedPrompt,
    output: Path | None,
) -> None:
    from llmm import llm_client
    from llmm.dialog import Message

    text = sys.stdin.read()
    content = prompt_module.render(parsed.user_template, text=text)

    if isinstance(content, list):
        messages: list = [{"role": "user", "content": content}]
    else:
        messages = [Message(role="user", content=content)]

    try:
        result = llm_client.complete(messages, cfg, system_prompt=parsed.system)
    except Exception as exc:  # noqa: BLE001
        console.print_error(str(exc))
        sys.exit(1)

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(result, encoding="utf-8")
    else:
        print(result)


def _cmd_chat(args: argparse.Namespace, cfg: config_module.Config) -> None:
    from llmm import scenario2
    from llmm.dialog import Dialog

    dialogs_dir = args.dialogs_dir if args.dialogs_dir is not None else Path.cwd()
    parsed = _require_prompt(args.prompt, dialogs_dir)
    effective_cfg = prompt_module.apply_overrides(cfg, parsed.config_overrides)

    dialog = Dialog(
        system_prompt=parsed.system,
        task=parsed.task,
        user_role=parsed.user_role,
        assistant_role=parsed.assistant_role,
    )

    scenario2.run(effective_cfg, dialog, dialogs_dir)


def _cmd_export(args: argparse.Namespace, cfg: config_module.Config) -> None:
    import jinja2

    from llmm import serializer
    from llmm.dialog import Dialog, Message, load_dialog

    if args.dialogs_dir is not None:
        # ---- Directory mode -------------------------------------------------
        dialogs_dir: Path = args.dialogs_dir
        template_path = _resolve_template(args.template, dialogs_dir)
        if template_path is None:
            console.print_error(
                f"Template file 'template.jinja' not found in {dialogs_dir}. "
                "Specify a path with --template."
            )
            sys.exit(1)

        template = jinja2.Template(template_path.read_text(encoding="utf-8"))
        out_dir = args.serialized_dir if args.serialized_dir is not None else dialogs_dir

        dialog_files = sorted(dialogs_dir.glob("*.dlg.toml"))
        if not dialog_files:
            console.print_info(f"No .dlg.toml files found in {dialogs_dir}.")
            return

        for dlg_file in dialog_files:
            try:
                dialog = load_dialog(dlg_file)
                output = serializer.serialize(template, dialog)
                # Replace .toml → .md  (e.g. dialog_20240101_120000.dlg.toml → .dlg.md)
                out_path = out_dir / dlg_file.name.replace(".toml", ".md")
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(output, encoding="utf-8")
            except Exception as exc:  # noqa: BLE001
                console.print_error(f"Error exporting {dlg_file}: {exc}")

    else:
        # ---- Single-dialog mode ---------------------------------------------
        if args.dialog is not None:
            dialog = load_dialog(args.dialog)
            lookup_dir = args.dialog.parent
        else:
            # Read dialog from stdin
            import tomlkit

            raw = sys.stdin.read()
            data = tomlkit.loads(raw)
            prompt_sect = data.get("prompt", {})
            role_names = data.get("role_names", {})
            chat = data.get("chat", {})
            dialog = Dialog(
                system_prompt=prompt_sect.get("system") or None,
                task=chat.get("task") or None,
                user_role=str(role_names.get("user", "user")),
                assistant_role=str(role_names.get("assistant", "assistant")),
                messages=[
                    Message(role=m["role"], content=m["content"])
                    for m in data.get("messages", [])
                ],
            )
            lookup_dir = Path.cwd()

        template_path = _resolve_template(args.template, lookup_dir)
        if template_path is None:
            console.print_error(
                f"Template file 'template.jinja' not found in {lookup_dir}. "
                "Specify a path with --template."
            )
            sys.exit(1)

        template = jinja2.Template(template_path.read_text(encoding="utf-8"))
        output = serializer.serialize(template, dialog)

        if args.serialized is not None:
            args.serialized.parent.mkdir(parents=True, exist_ok=True)
            args.serialized.write_text(output, encoding="utf-8")
        else:
            print(output)
