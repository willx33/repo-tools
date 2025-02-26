"""Notification utilities for repo tools."""

from rich.console import Console

console = Console()


def show_toast(message: str) -> None:
    """
    Show a toast notification.
    
    Args:
        message: The message to display.
    """
    console.print(f"[bold green]{message}[/bold green]")
    
    # Platform-specific toast notification could be added here
    # For example, using plyer library for cross-platform notifications
    # But for simplicity, we'll just use console output for now