"""Menu system for repo tools."""

import inquirer
from rich.console import Console

from repo_tools.modules.context_copier import repo_context_copier
from repo_tools.modules.github_context_copier import github_repo_context_copier

console = Console()


def display_main_menu() -> None:
    """Display the main menu and handle user selection."""
    while True:
        questions = [
            inquirer.List(
                "module",
                message="Select a module",
                choices=[
                    ("Local Repo Code Context Copier", "context_copier"),
                    ("GitHub Repo Code Context Copier", "github_context_copier"),
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
        elif module == "github_context_copier":
            github_repo_context_copier()
        else:
            console.print(f"[red]Unknown module: {module}[/red]")