"""Command line interface for repo tools."""

import sys
from rich.console import Console

from repo_tools.menu import display_main_menu

console = Console()


def main() -> int:
    """Run the CLI application."""
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