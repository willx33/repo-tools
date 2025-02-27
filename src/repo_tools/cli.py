"""Command line interface for repo tools."""

import sys
import atexit
from rich.console import Console

from repo_tools.menu import display_main_menu
from repo_tools.webui import stop_webui

console = Console()


def main() -> int:
    """Run the CLI application."""
    # Register shutdown function to ensure WebUI is stopped
    atexit.register(stop_webui)
    
    try:
        display_main_menu()
        return 0
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Process cancelled by user.[/bold yellow]")
        return 1
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")
        return 1


if __name__ == "__main__":
    sys.exit(main())