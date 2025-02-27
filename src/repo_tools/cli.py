"""Command line interface for repo tools."""

import sys
import atexit
import argparse
from rich.console import Console

from repo_tools.menu import display_main_menu
from repo_tools.webui import start_webui, stop_webui

console = Console()


def main() -> int:
    """Run the CLI application."""
    # Register shutdown function to ensure WebUI is stopped
    atexit.register(stop_webui)
    
    # Set up command-line argument parser
    parser = argparse.ArgumentParser(description='Repository tools for AI workflow')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # WebUI command
    webui_parser = subparsers.add_parser('webui', help='Start the web UI')
    webui_parser.add_argument(
        '--debug', 
        action='store_true', 
        help='Run the web UI in debug mode'
    )
    webui_parser.add_argument(
        '--no-browser', 
        action='store_true', 
        help='Do not automatically open the browser'
    )
    webui_parser.add_argument(
        '--background',
        action='store_true',
        help='Run the web UI in background mode (non-blocking)'
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    try:
        # Handle commands if provided
        if args.command == 'webui':
            debug = args.debug
            open_browser = not args.no_browser
            block = not args.background
            console.print("[bold green]Starting WebUI...[/bold green]")
            start_webui(debug=debug, open_browser=open_browser, block=block)
            if not block:
                console.print(f"[green]WebUI is running at http://127.0.0.1:5000/[/green]")
                console.print("[cyan]The WebUI will remain active until you exit this program.[/cyan]")
                console.print("[cyan]You can continue using the CLI while the WebUI is running.[/cyan]")
                display_main_menu()
            return 0
        else:
            # No command specified, show the interactive menu
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