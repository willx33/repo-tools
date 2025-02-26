"""Clipboard utilities for repo tools."""

import pyperclip


def copy_to_clipboard(text: str) -> None:
    """
    Copy text to clipboard.
    
    Args:
        text: The text to copy.
    """
    pyperclip.copy(text)