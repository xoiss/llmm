from __future__ import annotations

from pathlib import Path
from typing import Union

from llmm import console, llm_client
from llmm import prompt as prompt_module
from llmm.config import Config
from llmm.dialog import Message
from llmm.prompt import ParsedPrompt


def run(
    config: Config,
    parsed: ParsedPrompt,
    input_files: list[Path],
    output_files: list[Path | None],
) -> None:
    """Process each input file and write the LLM result to the corresponding output.

    A None output path causes the result to be written to stdout.
    Per-file errors are reported to stderr; processing continues for remaining files.
    """
    for input_path, output_path in zip(input_files, output_files):
        try:
            _process_file(config, parsed, input_path, output_path)
        except Exception as exc:  # noqa: BLE001
            console.print_error(f"Error processing {input_path}: {exc}")


def _process_file(
    config: Config,
    parsed: ParsedPrompt,
    input_path: Path,
    output_path: Path | None,
) -> None:
    ext = input_path.suffix.lower()

    if ext in prompt_module.SUPPORTED_IMAGE_EXTENSIONS:
        image = prompt_module.ImageData(input_path)
        content = prompt_module.render(parsed.user_template, image=image)
    else:
        text = input_path.read_text(encoding="utf-8")
        content = prompt_module.render(parsed.user_template, text=text)

    if isinstance(content, list):
        messages: list[Union[Message, dict]] = [{"role": "user", "content": content}]
    else:
        messages = [Message(role="user", content=content)]

    result = llm_client.complete(messages, config, system_prompt=parsed.system)

    if output_path is None:
        print(result)
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(result, encoding="utf-8")
