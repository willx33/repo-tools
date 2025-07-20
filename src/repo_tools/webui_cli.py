"""Command line entry point for directly launching the web UI."""

import sys
import atexit
import argparse
from rich.console import Console

from repo_tools.webui import start_webui, stop_webui, is_webui_running, get_webui_url

console = Console()


def main() -> int:
    """Run the web UI directly."""
    # Register shutdown function to ensure WebUI is stopped
    atexit.register(stop_webui)
    
    # Set up command-line argument parser
    parser = argparse.ArgumentParser(description='Repository Tools Web UI')
    parser.add_argument(
        '--debug', 
        action='store_true', 
        help='Run the web UI in debug mode'
    )
    parser.add_argument(
        '--no-browser', 
        action='store_true', 
        help='Do not automatically open the browser'
    )
    parser.add_argument(
        '--background',
        action='store_true',
        help='Run the web UI in background mode (non-blocking)'
    )
    parser.add_argument(
        '--host',
        default='127.0.0.1',
        help='Host to bind to (default: 127.0.0.1)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help='Port to bind to (default: 5000)'
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    try:
        # Launch the web UI directly
        debug = args.debug
        open_browser = not args.no_browser
        block = not args.background
        
        console.print("[bold green]Starting Repository Tools Web UI...[/bold green]")
        start_webui(debug=debug, open_browser=open_browser, block=block, host=args.host, port=args.port)
        
        # If running in background mode, show URL and exit
        if not block and is_webui_running():
            webui_url = get_webui_url()
            console.print(f"[green]Web UI is running at {webui_url}[/green]")
            console.print("[cyan]The Web UI will remain active until you exit this program.[/cyan]")
            console.print("[cyan]Press Ctrl+C to stop the server and exit.[/cyan]")
            
            # Wait for keyboard interrupt
            try:
                # This keeps the main thread alive while the web UI runs in the background
                import time
                while is_webui_running():
                    time.sleep(1)
            except KeyboardInterrupt:
                console.print("\n[bold yellow]Shutting down Web UI...[/bold yellow]")
                stop_webui()
        
        return 0
        
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Process cancelled by user.[/bold yellow]")
        return 1
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 