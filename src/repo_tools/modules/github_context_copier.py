"""GitHub repository code context copier module."""

import os
import re
import inquirer
import tempfile
import subprocess
from pathlib import Path
from rich.console import Console
from rich.progress import Progress
from rich.panel import Panel
from rich.text import Text

from repo_tools.utils.clipboard import copy_to_clipboard
from repo_tools.utils.notifications import show_toast

console = Console()

# Regular expression to extract GitHub repository URL from various formats
GITHUB_URL_PATTERN = r"(?:https?://)?(?:www\.)?github\.com/([^/]+)/([^/\s?]+)"


def extract_github_repo_url(input_url: str) -> str:
    """
    Extract a clean GitHub repository URL from user input.
    
    Args:
        input_url: User-provided URL or string that might contain a GitHub URL
        
    Returns:
        A clean GitHub repository URL or None if no valid URL found
    """
    match = re.search(GITHUB_URL_PATTERN, input_url)
    if match:
        owner, repo = match.groups()
        # Remove .git suffix if present
        repo = repo.replace('.git', '')
        return f"https://github.com/{owner}/{repo}"
    return None


def clone_github_repo(repo_url: str) -> Path:
    """
    Clone a GitHub repository to a temporary directory.
    
    Args:
        repo_url: The GitHub repository URL
        
    Returns:
        Path to the cloned repository or None if clone failed
    """
    temp_dir = Path(tempfile.mkdtemp())
    try:
        with Progress() as progress:
            task = progress.add_task("[green]Cloning repository...", total=None)
            
            # Run git clone
            result = subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, str(temp_dir)],
                capture_output=True,
                text=True,
                check=False
            )
            
            progress.update(task, completed=True)
            
            if result.returncode != 0:
                console.print(f"[bold red]Error cloning repository:[/bold red] {result.stderr}")
                return None
            
            return temp_dir
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        return None


def get_relevant_files_with_content(repo_path: Path):
    """
    Get all relevant files with their content from a repository.
    
    Args:
        repo_path: The path to the cloned repository
        
    Returns:
        A tuple containing:
        - A list of tuples (rel_path, content) for included files
        - A list of relative paths for ignored files
    """
    included_files = []
    ignored_files = []
    
    # File extensions that are likely source code
    included_extensions = [
        # Web
        ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".scss", ".sass", ".less",
        # Backend
        ".py", ".rb", ".php", ".java", ".go", ".rs", ".c", ".cpp", ".h", ".hpp",
        ".cs", ".fs", ".swift", ".kt", ".kts", ".scala", ".clj", ".ex", ".exs",
        # Config/Data
        ".json", ".yml", ".yaml", ".toml", ".ini", ".env.example", ".sql",
        # Documentation
        ".md", ".mdx", ".rst", ".txt"
    ]
    
    # Special files to always include regardless of extension
    important_filenames = [
        "README", "CONTRIBUTING", "ARCHITECTURE", "Dockerfile", "docker-compose.yml",
        "Makefile", "rakefile", "Rakefile", "CMakeLists.txt", "requirements.txt",
        "go.mod", "go.sum", "build.gradle", "pom.xml", "build.sbt", "Cargo.toml"
    ]
    
    # Directories to exclude
    excluded_dirs = [
        ".git", "node_modules", "venv", "env", ".env", ".venv", ".tox", 
        "__pycache__", "dist", "build", "target", "vendor", "deps",
        "bin", "obj", "packages", "third_party", "third-party", "external"
    ]
    
    for root, dirs, files in os.walk(repo_path):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in excluded_dirs]
        
        rel_root = os.path.relpath(root, repo_path)
        
        for file in files:
            rel_path = os.path.join(rel_root, file)
            abs_path = os.path.join(root, file)
            
            # Skip files in specific paths
            should_skip = False
            for excluded_dir in excluded_dirs:
                if f"/{excluded_dir}/" in f"/{rel_path}/":
                    should_skip = True
                    break
            
            if should_skip:
                ignored_files.append(rel_path)
                continue
            
            # Check if it's an important file by name
            is_important = False
            for name in important_filenames:
                if file.startswith(name):
                    is_important = True
                    break
            
            # Check extension if not important by name
            if not is_important:
                file_ext = os.path.splitext(file)[1].lower()
                if file_ext not in included_extensions:
                    ignored_files.append(rel_path)
                    continue
            
            try:
                with open(abs_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                
                # Skip empty files
                if not content.strip():
                    ignored_files.append(rel_path)
                    continue
                
                included_files.append((rel_path, content))
            except (UnicodeDecodeError, PermissionError, IsADirectoryError):
                # Skip binary files or files we can't read
                ignored_files.append(rel_path)
    
    return included_files, ignored_files


def display_file_summary(included_files, ignored_files):
    """
    Display a summary of included and ignored files.
    
    Args:
        included_files: List of tuples (file_path, content) for included files
        ignored_files: List of file paths that were ignored
    """
    # Group files by top-level directory
    included_by_dir = {}
    ignored_by_dir = {}
    
    # Process included files
    for file_path, _ in included_files:
        parts = file_path.split(os.sep)
        if len(parts) > 1:
            top_dir = parts[0]
        else:
            top_dir = "root"  # Files directly in repo root
        
        if top_dir not in included_by_dir:
            included_by_dir[top_dir] = []
        included_by_dir[top_dir].append(file_path)
    
    # Process ignored files
    for file_path in ignored_files:
        parts = file_path.split(os.sep)
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


def github_repo_context_copier() -> None:
    """Run the GitHub repo code context copier module."""
    # Track selected repositories and their content
    selected_repos = []
    
    while True:
        # Ask for GitHub repository URL
        questions = [
            inquirer.Text(
                "repo_url",
                message="Enter GitHub repository URL (or type 'back' to return to menu)",
            ),
        ]
        
        answers = inquirer.prompt(questions)
        
        if not answers:  # User pressed Ctrl+C
            break
            
        repo_url = answers["repo_url"].strip()
        
        if repo_url.lower() == 'back':
            break
        
        # Extract GitHub repository URL
        clean_url = extract_github_repo_url(repo_url)
        if not clean_url:
            console.print("[bold red]Invalid GitHub repository URL![/bold red]")
            continue
        
        console.print(f"[bold blue]Processing GitHub repository:[/bold blue] {clean_url}")
        
        # Clone the repository
        repo_path = clone_github_repo(clean_url)
        if not repo_path:
            continue
        
        # Get repository name from URL
        repo_name = clean_url.split('/')[-1]
        
        # Get all relevant files with content and ignored files
        with Progress() as progress:
            task = progress.add_task("[green]Reading repository files...", total=None)
            files_with_content, ignored_files = get_relevant_files_with_content(repo_path)
            progress.update(task, completed=True)
        
        # Display file summary
        display_file_summary(files_with_content, ignored_files)
        
        # Ask what to do next
        next_action_choices = [
            ("Copy to clipboard", "copy"),
            ("Add another repository", "add"),
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
        
        # Add the current repo to the selection
        selected_repos.append((repo_name, clean_url, files_with_content, ignored_files))
        console.print(f"[bold green]Added '{repo_name}' to selection[/bold green]")
        
        if next_action == "back":
            break
        elif next_action == "copy":
            # Copy all selected repos
            copy_selected_repositories(selected_repos)
            break
        # For "add", just continue the loop to select more repos
        
        # Clean up the temporary directory
        try:
            subprocess.run(["rm", "-rf", str(repo_path)], check=False)
        except Exception:
            pass


def copy_selected_repositories(selected_repos):
    """
    Copy content from all selected repositories to clipboard.
    
    Args:
        selected_repos: List of tuples (repo_name, repo_url, files_with_content, ignored_files)
    """
    if not selected_repos:
        console.print("[bold yellow]No repositories selected to copy.[/bold yellow]")
        return
    
    # Format content for clipboard with clear separation between repositories
    formatted_content = ""
    
    for repo_name, repo_url, files_with_content, ignored_files in selected_repos:
        # Add a repository header with separator
        formatted_content += f"\n{'=' * 80}\n"
        formatted_content += f"REPOSITORY: {repo_name} ({repo_url})\n"
        formatted_content += f"{'=' * 80}\n\n"
        
        # Add all files from this repo
        for rel_path, content in files_with_content:
            formatted_content += f"{rel_path}:\n{content}\n\n"
    
    # Copy to clipboard
    copy_to_clipboard(formatted_content)
    
    # Show toast notification
    repo_names = ', '.join([repo_name for repo_name, _, _, _ in selected_repos])
    show_toast(f"GitHub repositories copied to clipboard: {repo_names}")
    
    # Display summary
    total_files = sum(len(files) for _, _, files, _ in selected_repos)
    total_ignored = sum(len(ignored) for _, _, _, ignored in selected_repos)
    
    console.print(Panel(
        Text.from_markup(
            f"[bold green]{len(selected_repos)} repositories copied to clipboard[/bold green]\n"
            f"[green]• {total_files}[/green] files included\n"
            f"[yellow]• {total_ignored}[/yellow] files ignored"
        ),
        title="Copy Complete",
        border_style="green"
    ))