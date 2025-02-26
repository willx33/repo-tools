"""Repository code context copier module."""

import os
import inquirer
from pathlib import Path
from rich.console import Console
from rich.progress import Progress
from rich.panel import Panel
from rich.text import Text

from repo_tools.utils.git import find_git_repos, get_repo_name
from repo_tools.utils.git import get_relevant_files_with_content
from repo_tools.utils.clipboard import copy_to_clipboard
from repo_tools.utils.notifications import show_toast

console = Console()


def generate_path_options(start_path: Path) -> list:
    """
    Generate a list of path options going from current path to root.
    
    Args:
        start_path: Starting path
        
    Returns:
        List of tuples (path_display, path_object)
    """
    path_options = []
    current = start_path.absolute()
    
    # Add current and all parent paths until root
    while current != current.parent:
        path_options.append((str(current), current))
        current = current.parent
    
    # Add root
    path_options.append((str(current), current))
    
    return path_options


def display_file_summary(included_files, ignored_files, repo_path):
    """
    Display a summary of included and ignored files.
    
    Args:
        included_files: List of tuples (file_path, content) for included files
        ignored_files: List of file paths that were ignored
        repo_path: Path to the repository root
    """
    # Group files by top-level directory (depth of 1)
    included_by_dir = {}
    ignored_by_dir = {}
    repo_str = str(repo_path).rstrip(os.sep) + os.sep
    
    # Process included files
    for file_path, _ in included_files:
        # Get the path relative to the repo root
        rel_path = str(file_path)
        if rel_path.startswith(repo_str):
            rel_path = rel_path[len(repo_str):]
        
        # Get the top-level directory
        parts = rel_path.split(os.sep)
        if len(parts) > 1:
            top_dir = parts[0]
        else:
            top_dir = "root"  # Files directly in repo root
        
        if top_dir not in included_by_dir:
            included_by_dir[top_dir] = []
        included_by_dir[top_dir].append(file_path)
    
    # Process ignored files
    for file_path in ignored_files:
        # Get the path relative to the repo root
        rel_path = str(file_path)
        if rel_path.startswith(repo_str):
            rel_path = rel_path[len(repo_str):]
        
        # Get the top-level directory
        parts = rel_path.split(os.sep)
        if len(parts) > 1:
            top_dir = parts[0]
        else:
            top_dir = "root"  # Files directly in repo root
        
        if top_dir not in ignored_by_dir:
            ignored_by_dir[top_dir] = []
        ignored_by_dir[top_dir].append(file_path)
    
    # Display included files first
    console.print(f"\n[bold green]Files to be included:[/bold green]")
    for file_path, _ in included_files:
        console.print(f"  [green]✓[/green] {file_path}")
    
    # Then show the total count
    included_count = len(included_files)
    console.print(f"[bold green]Total: {included_count} files included[/bold green]\n")
    
    # Display ignored files count
    ignored_count = len(ignored_files)
    console.print(f"[bold yellow]Total: {ignored_count} files ignored[/bold yellow]\n")
    
    # Create summary by top-level directory
    console.print("[bold blue]Summary by directory:[/bold blue]")
    
    # Get all unique top-level directories
    all_dirs = set(list(included_by_dir.keys()) + list(ignored_by_dir.keys()))
    
    for directory in sorted(all_dirs):
        included_count = len(included_by_dir.get(directory, []))
        ignored_count = len(ignored_by_dir.get(directory, []))
        
        # Skip directories with no files
        if included_count == 0 and ignored_count == 0:
            continue
        
        display_dir = directory
        if display_dir == "root":
            display_dir = "(repo root)"
            
        # Create appropriate message based on what's included/excluded
        if included_count > 0 and ignored_count > 0:
            console.print(f"  [blue]•[/blue] {included_count} files included and {ignored_count} files ignored from [bold]{display_dir}/[/bold]")
        elif included_count > 0:
            console.print(f"  [green]•[/green] {included_count} files included from [bold]{display_dir}/[/bold]")
        elif ignored_count > 0:
            console.print(f"  [yellow]•[/yellow] {ignored_count} files ignored from [bold]{display_dir}/[/bold]")


def repo_context_copier() -> None:
    """Run the repo code context copier module."""
    # Get current directory
    current_dir = Path.cwd()
    
    # Generate path options
    path_options = generate_path_options(current_dir)
    path_options.append(("Back to main menu", None))
    
    # Ask user to select a path
    questions = [
        inquirer.List(
            "path",
            message="Select a path to search for repositories",
            choices=path_options,
        ),
    ]
    
    answers = inquirer.prompt(questions)
    
    if not answers or answers["path"] is None:  # User canceled or chose to go back
        return
    
    selected_path = answers["path"]
    console.print(f"[bold blue]Searching for repositories in:[/bold blue] {selected_path}")
    
    # Find git repositories
    with Progress() as progress:
        task = progress.add_task("[green]Scanning for git repositories...", total=None)
        repos = find_git_repos(selected_path)
        progress.update(task, completed=True)
    
    if not repos:
        console.print("[bold yellow]No git repositories found![/bold yellow]")
        return
    
    # Track selected repositories and their content
    selected_repos = []
    
    while True:
        # Prepare choices for the menu
        repo_choices = [(get_repo_name(repo), repo) for repo in repos if repo not in [r[0] for r in selected_repos]]
        
        # If there are already selected repos, show an option to copy them
        if selected_repos:
            selected_names = ", ".join([get_repo_name(repo) for repo, _, _ in selected_repos])
            copy_option = (f"Copy {len(selected_repos)} selected repositories ({selected_names})", "copy")
            repo_choices.insert(0, copy_option)
        
        repo_choices.append(("Back to main menu", None))
        
        # Show how many repos are selected if any
        if selected_repos:
            message = f"Select another repository (already selected: {len(selected_repos)})"
        else:
            message = "Select a repository to copy"
        
        questions = [
            inquirer.List(
                "repo",
                message=message,
                choices=repo_choices,
            ),
        ]
        
        answers = inquirer.prompt(questions)
        
        if not answers:  # User pressed Ctrl+C
            break
            
        selected_repo = answers["repo"]
        
        if selected_repo is None:  # Back to main menu
            break
            
        if selected_repo == "copy":  # Copy all selected repos
            # Process the copy operation
            copy_selected_repositories(selected_repos)
            break
        
        # Get all relevant files with content and ignored files
        with Progress() as progress:
            task = progress.add_task("[green]Reading repository files...", total=None)
            try:
                # Try the new version first (returns a tuple)
                files_with_content, ignored_files = get_relevant_files_with_content(selected_repo)
            except ValueError:
                # Fallback for old version (returns just one value)
                files_with_content = get_relevant_files_with_content(selected_repo)
                ignored_files = []
            progress.update(task, completed=True)
        
        # Display file summary
        display_file_summary(files_with_content, ignored_files, selected_repo)
        
        # Ask what to do next with simpler options
        next_action_choices = [
            ("Copy to clipboard", "copy"),
            ("Continue selecting", "add"),
            ("Back to main menu", "back")
        ]
        
        questions = [
            inquirer.List(
                "next_action",
                message="What would you like to do?",
                choices=next_action_choices,
                default="copy"  # Make "Copy to clipboard" the default selected option
            ),
        ]
        
        answers = inquirer.prompt(questions)
        
        if not answers:  # User pressed Ctrl+C
            break
            
        next_action = answers["next_action"]
        
        # Always add the current repo to the selection
        repo_name = get_repo_name(selected_repo)
        selected_repos.append((selected_repo, files_with_content, ignored_files))
        console.print(f"[bold green]Added '{repo_name}' to selection[/bold green]")
        
        if next_action == "back":
            break
        elif next_action == "copy":
            # Copy all selected repos
            copy_selected_repositories(selected_repos)
            break
        # For "add", just continue the loop to select more repos


def copy_selected_repositories(selected_repos):
    """
    Copy content from all selected repositories to clipboard.
    
    Args:
        selected_repos: List of tuples (repo_path, files_with_content, ignored_files)
    """
    if not selected_repos:
        console.print("[bold yellow]No repositories selected to copy.[/bold yellow]")
        return
    
    # Format content for clipboard with clear separation between repositories
    formatted_content = ""
    
    for repo_path, files_with_content, ignored_files in selected_repos:
        repo_name = get_repo_name(repo_path)
        
        # Add a repository header with separator
        formatted_content += f"\n{'=' * 80}\n"
        formatted_content += f"REPOSITORY: {repo_name}\n"
        formatted_content += f"{'=' * 80}\n\n"
        
        # Add all files from this repo
        for file_path, content in files_with_content:
            abs_path = os.path.abspath(file_path)
            formatted_content += f"{abs_path}:\n{content}\n\n"
    
    # Copy to clipboard
    copy_to_clipboard(formatted_content)
    
    # Show toast notification
    repo_names = ', '.join([get_repo_name(repo) for repo, _, _ in selected_repos])
    show_toast(f"Repositories copied to clipboard: {repo_names}")
    
    # Display summary
    total_files = sum(len(files) for _, files, _ in selected_repos)
    total_ignored = sum(len(ignored) for _, _, ignored in selected_repos)
    
    console.print(Panel(
        Text.from_markup(
            f"[bold green]{len(selected_repos)} repositories copied to clipboard[/bold green]\n"
            f"[green]• {total_files}[/green] files included\n"
            f"[yellow]• {total_ignored}[/yellow] files ignored"
        ),
        title="Copy Complete",
        border_style="green"
    ))