"""Menu system for repo tools."""

import os
import inquirer
from rich.console import Console
from rich.align import Align
from rich.text import Text

from repo_tools.modules.context_copier import repo_context_copier
from repo_tools.modules.github_context_copier import github_repo_context_copier

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
                repo_context_copier()
                console.print("[green]Local repo context copied successfully![/green]")
            elif module == "github_context_copier":
                console.print("[bold green]GitHub Repo Code Context Copier[/bold green]")
                github_repo_context_copier()
                console.print("[green]GitHub repo context copied successfully![/green]")
            else:
                console.print(f"[red]Unknown module: {module}[/red]")
            
            # Pause for user to see results
            console.print("\n[cyan]Press Enter to continue...[/cyan]")
            input()
    finally:
        # Ensure we leave the screen clean
        clear_screen()