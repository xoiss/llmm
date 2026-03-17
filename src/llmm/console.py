from __future__ import annotations

import sys

import colorama
from colorama import Fore, Style

colorama.init()


def print_user(text: str) -> None:
    """Print user message in default terminal color to stdout."""
    print(text)


def print_llm(text: str) -> None:
    """Print LLM/assistant response in cyan to stdout."""
    print(Fore.CYAN + text + Style.RESET_ALL)


def print_info(text: str) -> None:
    """Print informational/status message in yellow to stdout."""
    print(Fore.YELLOW + text + Style.RESET_ALL)


def print_error(text: str) -> None:
    """Print error message in red to stderr."""
    print(Fore.RED + text + Style.RESET_ALL, file=sys.stderr)
