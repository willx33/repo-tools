"""Menu system for repo tools."""

import inquirer
from rich.console import Console

from repo_tools.modules.context_copier import repo_context_copier

console = Console()


def display_main_menu() -> None:
    """Display the main menu and handle user selection."""
    while True:
        questions = [
            inquirer.List(
                "module",
                message="Select a module",
                choices=[
                    ("Repo Code Context Copier", "context_copier"),
                    ("Exit", "exit"),
                ],
            ),
        ]

        answers = inquirer.prompt(questions)
        
        if not answers:  # User pressed Ctrl+C
            break
            
        module = answers["module"]
        
        if module == "exit":
            console.print("[yellow]Exiting...[/yellow]")
            break
        elif module == "context_copier":
            repo_context_copier()
        else:
            console.print(f"[red]Unknown module: {module}[/red]")