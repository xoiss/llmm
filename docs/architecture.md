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
    |       +-- config.py           <- config loading (env vars + TOML file)
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

    llmm run [--prompt PROMPT_FILE] [--document DOCUMENT_FILE | --image IMAGE_FILE] [--output OUTPUT_FILE]
    llmm run [--prompt PROMPT_FILE] --input-dir INPUT_DIR [--output-dir OUTPUT_DIR]

**Single-document mode** (first form):

- `--prompt PROMPT_FILE`: prompt file. If omitted, `.prompt` is looked up in the
  directory of `--document` or `--image`; if the document is read from stdin, in the
  current working directory.
- `--document DOCUMENT_FILE`: text document (`.txt`, `.md`) substituted into the prompt
  template. Mutually exclusive with `--image`.
- `--image IMAGE_FILE`: image file (`.png`, `.jpg`) substituted into the prompt
  template. Mutually exclusive with `--document`.
- If neither `--document` nor `--image` is specified, the document is read from stdin
  (via pipe, file redirection, or interactive console input) as plain text.
- `--output OUTPUT_FILE`: output file path. If omitted, output is written to stdout.

**Directory mode** (second form):

- `--prompt PROMPT_FILE`: prompt file. If omitted, `.prompt` is looked up in `INPUT_DIR`.
- `--input-dir INPUT_DIR`: process all `.txt`/`.md`/`.png`/`.jpg` files in the
  directory. Use `.` to select the current working directory.
- `--output-dir OUTPUT_DIR`: directory for results; output file names inherit the input
  file stem with a `.out.md` extension. If omitted, output files are written to
  `INPUT_DIR`.

### `llmm chat`

    llmm chat [--prompt PROMPT_FILE] [--dialogs-dir DIALOGS_DIR]

- `--prompt PROMPT_FILE`: prompt file. If omitted, `.prompt` is looked up in
  `DIALOGS_DIR`.
- `--dialogs-dir DIALOGS_DIR`: directory where dialog files are saved. If omitted,
  dialog files are saved to the current working directory.

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

    llmm export [--prompt PROMPT_FILE] [--dialog DIALOG_FILE] [--serialized SERIALIZED_FILE]
    llmm export [--prompt PROMPT_FILE] --dialogs-dir DIALOGS_DIR [--serialized-dir SERIALIZED_DIR]

Converts one or more `.dlg.toml` dialog files to plain text with role names taken from
the `[roles]` section of the prompt file.

The same prompt file that was used with `llmm chat` when the dialog was recorded
should be passed here, ensuring role names are consistent with the original scenario.

**Single-dialog mode** (first form):

- `--prompt PROMPT_FILE`: prompt file. If omitted, `.prompt` is looked up in the
  directory of `--dialog`; if the dialog is read from stdin, in the current working
  directory.
- `--dialog DIALOG_FILE`: input `.dlg.toml` file produced by `llmm chat`. If omitted,
  the dialog is read from stdin.
- `--serialized SERIALIZED_FILE`: output `.dlg.md` file, suitable for use as a document
  in `llmm run`. If omitted, output is written to stdout.

**Directory mode** (second form):

- `--prompt PROMPT_FILE`: prompt file. If omitted, `.prompt` is looked up in
  `DIALOGS_DIR`.
- `--dialogs-dir DIALOGS_DIR`: directory to search for `*.dlg.toml` files. Use `.` to
  select the current working directory.
- `--serialized-dir SERIALIZED_DIR`: directory where serialized `.dlg.md` files are
  written. Output file names are derived from the input file names by replacing the
  `.toml` extension with `.md` (e.g. `dialog_20240101_120000.dlg.toml` →
  `dialog_20240101_120000.dlg.md`). If omitted, serialized files are written to
  `DIALOGS_DIR`.

If `--prompt` is omitted and no `.prompt` file is found in the lookup directory, the
command exits with an error indicating the expected file name and the directory where it
was looked up.

---

## Configuration

### Environment Variables

| Variable                        | Purpose                                                                       |
|---------------------------------|-------------------------------------------------------------------------------|
| `LLMM_PROVIDER_API_BASE_URL`    | Base URL of the LLM provider (e.g. `http://localhost:8080`)                   |
| `LLMM_PROVIDER_API_AUTH_TOKEN`  | Token for authenticating requests to the LLM provider API                     |
| `LLMM_PROVIDER_API_AUTH_TYPE`   | Token type prefix in the HTTP `Authorization` header (e.g. `Bearer`, `OAuth`) |

### Config File

Default location: `~/.llmm/config.toml`. Override with `--config FILE`.

File format: TOML.

**Config file values take precedence over environment variables.**

    [provider_api]
    base_url    = "https://api.example.com"
    auth_token  = "my-token"
    auth_type   = "Bearer"

    [llm_params]
    dialect               = "OpenAI Chat Completions"  # selects the API endpoint and request/response format
    model                 = "gpt-4o"
    temperature           = 0.7     # optional; range depends on dialect and model (OpenAI: 0 to 2)
    max_completion_tokens = 4096    # optional; maximum value depends on model

### Precedence (highest to lowest)

1. Prompt file (`[provider_api]`, `[llm_params]` sections)
2. Config file (`~/.llmm/config.toml`)
3. Environment variables
4. Built-in defaults

---

## File Formats

### Prompt File (`.prompt`)

TOML format. All keys are optional.

    [provider_api]
    # values defined here take precedence over the global config file

    [llm_params]
    # values defined here take precedence over the global config file

    [prompt]
    system = "You are a precise and concise assistant. Always respond in JSON."

    user = """
    Extract all named entities from the document below.
    Return a JSON object matching this schema:

    {
      "entities": [{"name": "...", "type": "..."}]
    }

    Document:
    {{ document }}
    """

    [roles]
    user      = "User"
    assistant = "Assistant"

The `[provider_api]` and `[llm_params]` sections mirror the corresponding sections of
the global config file. Any keys present here take precedence over the global config,
making the prompt file act as a local (per-scenario) config override.

The `[roles]` section defines the display names substituted for the `user` and
`assistant` roles when a dialog is serialized — both by `llmm export` and by the
`/history` command inside `llmm chat`. Keeping role names in the prompt file guarantees
they are consistent with the persona or scenario the dialog was designed for (e.g.,
`"Interviewer"` / `"Candidate"`, `"Doctor"` / `"Patient"`).

If `[roles]` is absent, the literal strings `"user"` and `"assistant"` are used as
fallback.

The `[prompt].user` value is a **Jinja2 template**. The `{{ document }}` placeholder is
the only variable injected during rendering. Literal `{` and `}` characters anywhere in
the template (JSON schemas, code examples, etc.) are passed through unchanged, since
Jinja2 only treats `{{` and `}}` as special.

**Template rendering rules:**

- For **text input** (`--document` with `.txt`/`.md`, or stdin): `{{ document }}` is
  replaced with the full UTF-8 text. The resulting string becomes the `content` field
  of the user message.
- For **image input** (`--image` with `.png`/`.jpg`): `{{ document }}` is removed from
  the template. The user message `content` field becomes a multimodal array:
  1. The remaining template text (trimmed) as a `{"type": "text", "text": "..."}` part.
     Omitted entirely when the remaining text is empty.
  2. The image as a `{"type": "image_url", "image_url": {"url": "data:<mime>;base64,<b64>"}}` part.
- If `[prompt].system` is absent, no system message is included in the API request.
- If `[prompt].user` is absent, the full document text (or the image alone) is sent as
  the sole user message.

### Dialog File (`.dlg.toml`)

TOML format. Written append-only during a live session. Stored in the directory
specified by `--dialogs-dir`, or in the current working directory if the option is
omitted.

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

- Reads the global TOML config file (path from `--config` or the default `~/.llmm/config.toml`).
- Reads `LLMM_PROVIDER_API_BASE_URL`, `LLMM_PROVIDER_API_AUTH_TOKEN`, and
  `LLMM_PROVIDER_API_AUTH_TYPE` from the environment.
- Merges both sources into a base `Config` dataclass.
- `Config` is subsequently merged with the prompt file's `[provider_api]` and
  `[llm_params]` overrides (handled in `prompt.py`) before being passed to other modules.

### `llm_client.py`

- Wraps `requests.post` to `<base_url>/chat/completions` (synchronous, non-streaming).
- Builds the `messages` list from a sequence of `Message` objects.
- Handles both plain-string and multimodal (content array) user messages.
- Sets `Authorization: <auth_type> <auth_token>`, `model`, and `temperature` from `Config`.
- Raises typed exceptions for HTTP-level and API-level errors.
- No retry logic in v1 — the caller decides on error handling.
- **v1 implements the `OpenAI Chat Completions` dialect only.** Dialect-specific logic
  (endpoint path, request/response format) must be isolated so that other OpenAI
  endpoints and non-OpenAI-compatible vendor dialects can be added in future versions
  without restructuring the rest of the codebase.

### `prompt.py`

- Parses a `.prompt` file and returns:
  - `[prompt].system: str | None` — system message text.
  - `[prompt].user: str | None` — Jinja2 user message template.
  - `[roles]`: `(user_role, assistant_role)` display names, defaulting to
    `("user", "assistant")` if the section is absent.
  - `[provider_api]` and `[llm_params]` key-value pairs as config overrides; merged
    on top of the base `Config` to produce the effective configuration for the run.
- `ImageData` dataclass: wraps an image and exposes a `uri` property that returns the
  ready-to-use data URI (`data:<mime>;base64,<b64>`). Internal storage and URI
  construction are implementation details of `ImageData`; `render()` only consumes
  `image.uri`.
- `render(user_template, text: str | None, image: ImageData | None) -> str | list[dict]`
  applies Jinja2 rendering with `document` as the sole template variable. The caller is
  responsible for reading the source (file or stdin) and supplying either `text` or
  `image`:
  - text input → plain string result of `Template(user_template).render(document=text)`.
  - image input → `{{ document }}` is rendered to an empty string; result is a multimodal
    content array (see File Formats section).

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
- Role names are supplied by the caller from the parsed prompt file.
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
    prompt.py --> (system, rendered_user_message)
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
| `jinja2`       | Template rendering for prompt files             | no     |
| `colorama`     | Cross-platform ANSI color support               | no     |
| `tomllib`      | TOML parser for config, prompt and dialog files | yes (3.11+) |
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
    dependencies    = ["requests", "jinja2", "colorama"]

    [project.scripts]
    llmm = "llmm.cli:main"

    [tool.hatch.build.targets.wheel]
    packages = ["src/llmm"]

The `src/` layout ensures the package is not importable from the repo root without
installation, preventing accidental imports during development without a proper install.
Use `pip install -e .` for an editable development install.
