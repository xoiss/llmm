# Architecture Design: `llmm`

## Overview

`llmm` is a cross-platform Python 3.11+ command-line utility for running LLM workflows.
It supports two operational modes — batch file processing (**Scenario 1**) and interactive
chat (**Scenario 2**) — plus a dialog export helper command.

The tool targets any LLM provider that exposes an OpenAI-compatible
`POST /chat/completions` HTTP endpoint with Bearer-token authentication.

---

## Repository Structure

    llmm/                           <- repo root
    +-- src/
    |   +-- llmm/                   <- installable package
    |       +-- __init__.py
    |       +-- __main__.py         <- `python -m llmm` entry point
    |       +-- cli.py              <- argument parser, subcommand routing
    |       +-- config.py           <- config loading (env vars + INI file)
    |       +-- llm_client.py       <- OpenAI-compatible HTTP client
    |       +-- prompt.py           <- prompt file parsing and template rendering
    |       +-- dialog.py           <- dialog data model and file I/O
    |       +-- scenario1.py        <- batch processing logic
    |       +-- scenario2.py        <- interactive chat loop and command handling
    |       +-- serializer.py       <- dialog to plain-text serialization
    |       +-- console.py          <- colored terminal output
    +-- docs/
    |   +-- implementation_requirements.md
    |   +-- architecture.md
    +-- tests/
    +-- pyproject.toml
    +-- README.md
    +-- .gitignore

---

## CLI Interface

    llmm [--config FILE] <command> [args...]

    Commands:
      run     Batch-process one file or a directory (Scenario 1)
      chat    Start an interactive dialog session (Scenario 2)
      export  Serialize a structured dialog file to plain text

### `llmm run`

    llmm run --prompt PROMPT_FILE INPUT_FILE  [--output OUTPUT_FILE] [--model MODEL]
    llmm run --prompt PROMPT_FILE INPUT_DIR   --output-dir OUTPUT_DIR [--model MODEL]

- `INPUT_FILE` / `INPUT_DIR`: accepted extensions are `.txt`, `.md`, `.png`, `.jpg`.
- `--output`: explicit output path (single-file mode only).
- `--output-dir`: directory for results (directory mode); output file names inherit the
  input file stem with a `.md` extension.
- `--model`: overrides the model name from the config file for this run.

### `llmm chat`

    llmm chat --prompt PROMPT_FILE [--model MODEL]

Starts an interactive console session. User input and special commands are both entered
at the same prompt and confirmed with **Enter**. Special commands begin with `/`:

| Command    | Action                                                                    |
|------------|---------------------------------------------------------------------------|
| `/new`     | Close the current dialog file and start a new dialog                      |
| `/back`    | Roll back the last user + assistant exchange (repeatable)                 |
| `/history` | Print the current in-memory dialog to the console                         |
| `/exit`    | Close the current dialog file and quit the program                        |

If `/back` is issued when no exchanges remain, a warning is printed and nothing changes.

### `llmm export`

    llmm export DIALOG_FILE [--output TEXT_FILE]

Converts a structured dialog file to plain text with role names substituted from the
config. Writes to stdout if `--output` is omitted.

---

## Configuration

### Environment Variables

| Variable            | Purpose                                                       |
|---------------------|---------------------------------------------------------------|
| `LLMM_API_BASE_URL` | Base URL of the LLM provider (e.g. `http://localhost:8080`)  |
| `LLMM_API_TOKEN`    | OAuth Bearer token                                            |

### Config File

Default location: `~/.llmm/config`. Override with `--config FILE`.

Format: INI (Python `configparser` — same syntax family as gitconfig).

**Config file values take precedence over environment variables.**

    [api]
    base_url    = https://api.example.com
    token       = my-oauth-token
    model       = gpt-4o

    [llm]
    temperature = 0.7

    [dialog]
    directory   = ~/llmm-dialogs      ; default: ~/.llmm/dialogs

    [roles]
    user        = User                ; substituted when exporting a dialog file
    assistant   = Assistant

### Precedence (highest to lowest)

1. CLI flag (e.g. `--model`)
2. Config file
3. Environment variables
4. Built-in defaults

---

## File Formats

### Prompt File (`.prompt`)

TOML format. Both keys are optional.

    system = "You are a precise and concise assistant."

    user = """
    Analyze the following document and produce a structured summary:

    {content}
    """

**Template rendering rules:**

- For **text files** (`.txt`, `.md`): `{content}` is replaced with the full UTF-8 file text.
  The resulting string becomes the `content` field of the user message (a plain string).
- For **image files** (`.png`, `.jpg`): `{content}` is removed from the template text.
  The user message `content` field becomes a multimodal array:
  1. The remaining template text (trimmed) as a `{"type": "text", "text": "..."}` part.
     Omitted entirely when the remaining text is empty.
  2. The image as a `{"type": "image_url", "image_url": {"url": "data:<mime>;base64,<b64>"}}` part.
- If `system` is absent, no system message is included in the API request.
- If `user` is absent, the full file text (or the image alone) is sent as the sole
  user message.

### Dialog File (`.dlg.toml`)

TOML format. Written append-only during a live session. Stored in the `dialog.directory`
from config.

**Naming convention:** `dialog_YYYYMMDD_HHMMSS.dlg.toml`
(timestamp is recorded when the first user message is written to the file).

**Format:**

    system = "You are a helpful assistant."

    [[messages]]
    role    = "user"
    content = "Hello!"

    [[messages]]
    role    = "assistant"
    content = "Hi there! How can I help you?"

    [[messages]]
    role    = "user"
    content = "Tell me about Python."

    [[messages]]
    role    = "assistant"
    content = "Python is a high-level, interpreted programming language..."

**Parsed with** `tomllib` (Python 3.11+ stdlib). The result is a dict with a `system`
string and a `messages` list of `{role, content}` dicts — matching the OpenAI
`/chat/completions` message structure directly.

**Appending a new turn** writes:

    \n[[messages]]\nrole    = "<role>"\ncontent = "<escaped content>"\n

Since TOML `[[array of tables]]` entries are simply concatenated, appending a block
to the end of the file always produces valid TOML. Content strings are written using
TOML basic string escaping (handled by `dialog.py` without a TOML writer library).

**Design rationale:**
- Human-readable without special tools.
- Standard parser (`tomllib`) — no custom parsing logic.
- Append-friendly: each `[[messages]]` block is independent.
- Can be fed into Scenario 1 after serialization via `llmm export`.

### Serialized Dialog File (plain text)

Output of `llmm export`. The system prompt section is **not** included (it is an internal
directive, not a conversational turn). Role names are substituted from `[roles]` in config.

    User:
    Hello!

    Assistant:
    Hi there! How can I help you?

    User:
    Tell me about Python.

    Assistant:
    Python is a high-level, interpreted programming language...

---

## Component Responsibilities

### `config.py`

- Reads the INI config file (path from `--config` or the default `~/.llmm/config`).
- Reads `LLMM_API_BASE_URL` and `LLMM_API_TOKEN` from the environment.
- Merges both sources, applying the precedence order.
- Exposes a single `Config` dataclass consumed by every other module.

### `llm_client.py`

- Wraps `requests.post` to `<base_url>/chat/completions` (synchronous, non-streaming).
- Builds the `messages` list from a sequence of `Message` objects.
- Handles both plain-string and multimodal (content array) user messages.
- Sets `Authorization: Bearer <token>`, `model`, and `temperature` from `Config`.
- Raises typed exceptions for HTTP-level and API-level errors.
- No retry logic in v1 — the caller decides on error handling.

### `prompt.py`

- Parses a `.prompt` file into `(system: str | None, user_template: str | None)`.
- `render(user_template, file_path) -> str | list[dict]` applies the substitution:
  - text file → plain string after `{content}` replacement.
  - image file → multimodal content array (see File Formats section).

### `dialog.py`

- `Message` dataclass: `role: str`, `content: str`.
- `Dialog` dataclass: `system_prompt: str | None`, `messages: list[Message]`.
  - `rollback()`: removes the last `(user, assistant)` pair from `messages`.
    Raises `RollbackError` when there is nothing to remove.
- `DialogWriter`: opens a file path, appends turns one at a time, closes on request.
  - The system prompt is written as the first block when the file is created.
- `load_dialog(path: Path) -> Dialog`: parses a `.dlg.toml` file.
- **Rollback file lifecycle**: on `/back`, the writer closes the current file.
  When the next user message arrives, a new file is opened and pre-populated by
  writing all turns from the in-memory `Dialog` (the rolled-back state) before
  appending the new turn.

### `scenario1.py`

- Collects input files: a single path or all `.txt`/`.md`/`.png`/`.jpg` files in a
  directory.
- For each input file:
  1. Renders the prompt via `prompt.py`.
  2. Calls `llm_client.complete(messages)`.
  3. Writes the LLM output to the corresponding output `.md` file.
- Per-file errors are reported to stderr (via `console.py`); processing continues for
  the remaining files.

### `scenario2.py`

- Runs the interactive REPL loop (reads from stdin, writes via `console.py`).
- Maintains a `Dialog` in memory and a `DialogWriter` for the current file.
- On user input: checks for a `/command` prefix; otherwise sends to the LLM.
- Command dispatch:
  - `/new`: close current writer, reset `Dialog`, next message opens a new file.
  - `/back`: call `Dialog.rollback()`; if `RollbackError`, print warning; close
    writer; next message opens a new file pre-populated with current `Dialog`.
  - `/history`: serialize `Dialog` to console using `serializer.py` with role names
    from config.
  - `/exit`: close writer and exit.

### `serializer.py`

- `serialize(dialog: Dialog, user_role: str, assistant_role: str) -> str`
- Formats each message as `<Role>:\n<text>\n\n`; skips the system prompt.
- Used by both `llmm export` (writes to file/stdout) and `/history` (writes to console).

### `console.py`

- Initializes `colorama` once for cross-platform ANSI support.
- Provides four print functions with consistent color coding:

| Function           | Color   | Purpose                          |
|--------------------|---------|----------------------------------|
| `print_user(text)` | default | Echo user input (if needed)      |
| `print_llm(text)`  | cyan    | Assistant response               |
| `print_info(text)` | yellow  | Service / status messages        |
| `print_error(text)`| red     | Runtime errors                   |

---

## Data Flow Diagrams

### Scenario 1 (Batch)

    CLI args
        |
        v
    config.py --> Config
        |
        v
    prompt.py --> (system, rendered_user_content)
        |
        v
    [for each input file]
        |
        +-- llm_client.py --> LLM API --> response text
        |
        +-- write OUTPUT_FILE.md

### Scenario 2 (Interactive Chat)

    CLI args
        |
        v
    config.py --> Config
        |
        v
    prompt.py --> system_prompt
        |
        v
    scenario2.py  <-- stdin (user input or /command)
        |
        +-- /command --> in-memory Dialog update + dialog.py (file I/O)
        |
        +-- user message --> llm_client.py --> LLM API --> response text
                                |
                                +-- dialog.py (append to .dlg.toml)
                                +-- console.py (print response)

---

## Dependencies

| Package        | Purpose                                         | stdlib |
|----------------|-------------------------------------------------|--------|
| `requests`     | HTTP client for the LLM API                     | no     |
| `colorama`     | Cross-platform ANSI color support               | no     |
| `tomllib`      | TOML parser for prompt and dialog files         | yes (3.11+) |
| `configparser` | INI parser for the main config file             | yes    |
| `argparse`     | CLI argument parsing                            | yes    |
| `pathlib`      | Path manipulation                               | yes    |
| `base64`       | Image encoding for multimodal input             | yes    |
| `datetime`     | Dialog file timestamps                          | yes    |

---

## `pyproject.toml` Structure

    [build-system]
    requires      = ["hatchling"]
    build-backend = "hatchling.build"

    [project]
    name            = "llmm"
    version         = "0.1.0"
    requires-python = ">=3.11"
    dependencies    = ["requests", "colorama"]

    [project.scripts]
    llmm = "llmm.cli:main"

    [tool.hatch.build.targets.wheel]
    packages = ["src/llmm"]

The `src/` layout ensures the package is not importable from the repo root without
installation, preventing accidental imports during development without a proper install.
Use `pip install -e .` for an editable development install.
