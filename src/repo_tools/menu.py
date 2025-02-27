"""Menu system for repo tools."""

import os
import datetime
import inquirer
from rich.console import Console
from rich.align import Align
from rich.text import Text

from repo_tools.modules.context_copier import repo_context_copier
from repo_tools.modules.github_context_copier import github_repo_context_copier
from repo_tools.webui import start_webui, stop_webui

console = Console()


def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def display_main_menu() -> None:
    """Display the main menu and handle user selection."""
    try:
        while True:
            # Clear screen for full-screen effect
            clear_screen()
            
            # Create a centered title
            title = Text("🛠️  REPO TOOLS  🛠️", style="bold cyan")
            console.print(Align.center(title, vertical="middle"))
            console.print()
            
            questions = [
                inquirer.List(
                    "module",
                    message="Select a module",
                    choices=[
                        ("Local Repo Code Context Copier", "context_copier"),
                        ("GitHub Repo Code Context Copier", "github_context_copier"),
                        ("Start WebUI", "webui"),
                        ("Exit", "exit"),
                    ],
                    carousel=True,  # Allow wrap-around navigation
                    default="context_copier",  # Start at the first item
                ),
            ]

            answers = inquirer.prompt(questions)
            
            if not answers:  # User pressed Ctrl+C
                break
                
            module = answers["module"]
            
            if module == "exit":
                console.print("[yellow]Exiting...[/yellow]")
                break
            
            # Run the selected module
            clear_screen()
            
            if module == "context_copier":
                console.print("[bold green]Local Repo Code Context Copier[/bold green]")
                success = repo_context_copier()
                if success:
                    console.print("[green]Local repo context copied successfully![/green]")
            elif module == "github_context_copier":
                console.print("[bold green]GitHub Repo Code Context Copier[/bold green]")
                success = github_repo_context_copier()
                if success:
                    console.print("[green]GitHub repo context copied successfully![/green]")
            elif module == "webui":
                console.print("[bold green]Starting WebUI...[/bold green]")
                # Start WebUI in background mode (non-blocking)
                start_webui(debug=False, open_browser=True, block=False)
                console.print(f"[green]WebUI is running at http://127.0.0.1:5000/[/green]")
                console.print("[cyan]The WebUI will remain active until you exit the program.[/cyan]")
                console.print("[cyan]You can continue using the CLI while the WebUI is running.[/cyan]")
            else:
                console.print(f"[red]Unknown module: {module}[/red]")
            
            # Pause for user to see results
            console.print("\n[cyan]Press Enter to continue...[/cyan]")
            input()
    finally:
        # Stop WebUI if it's running
        try:
            stop_webui()
        except:
            pass
        
        # Ensure we leave the screen clean
        clear_screen()