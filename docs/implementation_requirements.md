# Implementation requirements


## Scenario 1

The input is either a path to a single file or a path to a directory containing multiple identical files. These can be text files (.txt, .md extensions) or graphic files (.png, .jpg extensions).

The input also includes a prompt for LLM. The prompt can be split into two parts: system and user. The user part can have a single field for substituting the contents of a text file (see above). The prompt is also saved to a file. The format of such a file must be developed.

The program must call the specified generative LLM with this prompt once for each input file. Text or multimodal LLM can be used. The generation result is text.

The generation results must be saved to files (.md extension). The output file name is either specified directly if the program is called for a single input file, or is taken from the name of the processed input file. In the latter case, the program is given the path to the output directory.


## Scenario 2

The input is a simple system prompt for an LLM. The prompt is saved to a file.

The program implements an interactive dialogue with the user. After the user enters a message, the program calls the specified generative LLM, passing it the entire dialogue history and the system prompt. A text-based LLM is used. The generated output is also text. Multimodality is not required here.

Using special commands entered into the same interactive console, the user can: start a new dialogue (and simultaneously end the current dialogue), roll back one step (this command can be repeated multiple times until reaching the beginning of the dialogue), exit, or view the dialogue history (display it on the screen). Commands begin with the "/" character. User messages and commands are confirmed by pressing "Enter."

The current dialogue is written to a file. A new message from the user or the LLM is appended to the end of the file. The command to start a new dialogue (and end the current dialogue) closes the dialogue file. A new dialog file is created when the user enters their first message. The "roll back one step" command closes the current dialog file, and as soon as the user enters another message, a new dialog file is opened. This file pre-records the user and LLM's comments from the beginning of the dialog that were not canceled by the "roll back" command (or series of commands), and then continues with subsequent user and LLM messages. A format for this file, as well as a naming convention and storage location, must be developed. It should contain the system prompt and the user and LLM's comments as the "user" and "assistant" roles.

The program should also allow serialization of the structured dialog file into a text file, substituting the roles specified in the settings for the "user" and "assistant" roles.


## Helper functions

The program should allow serialization of a structured dialog file into a text file, substituting the roles specified in the settings for the "user" and "assistant" roles. This makes it possible to use LLM in scenario 1 to analyze the dialog that occurred in scenario 2.


## General Settings

The LLM provider exposes an OpenAI HTTP interface. The synchronous /chat/completions method is implemented. Authentication is performed via an OAuth token passed in the Authorization HTTP header.

The program configuration must allow the Base URL to the LLM provider to be set either via an environment variable or via a configuration file (the configuration file takes precedence). The same applies to the OAuth token. It is necessary to suggest names for the environment variables.

The program configuration must also allow setting the LLM temperature. The configuration file format must be human-readable. A format similar to gitconfig (or an INI file) is preferred.


## General Requirements

The application is a command-line utility. In interactive mode, it uses a text console to communicate with the user. Color can be used to visually distinguish user messages from LLM and other service messages (including runtime errors).

The application is written in Python 3.11 or higher and is cross-platform. Distribution is via PyPI, so you must initially create a directory structure in the repository that is compatible with the PyPI package build system.
