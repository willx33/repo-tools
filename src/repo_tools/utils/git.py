"""Git utilities for repo tools."""

import os
from pathlib import Path
from typing import List, Tuple, Set
import pathspec


def find_git_repos(directory: Path) -> List[Path]:
    """
    Find git repositories in the given directory.
    
    Args:
        directory: The directory to search in.
        
    Returns:
        A list of paths to git repositories.
    """
    repos = []
    
    for root, dirs, _ in os.walk(directory):
        if '.git' in dirs:
            repos.append(Path(root))
            # Don't search subdirectories of git repos
            dirs.remove('.git')
    
    return repos


def get_repo_name(repo_path: Path) -> str:
    """
    Get the name of a repository from its path.
    
    Args:
        repo_path: The path to the repository.
        
    Returns:
        The name of the repository.
    """
    return repo_path.name


def parse_gitignore(repo_path: Path) -> pathspec.PathSpec:
    """
    Parse all .gitignore files in a repository.
    
    Args:
        repo_path: The path to the repository.
        
    Returns:
        A PathSpec object representing the combined .gitignore rules.
    """
    patterns = []
    
    # Add default ignored patterns
    patterns.extend([
        ".git/",
        "**/__pycache__/",
        "**/*.py[cod]",
        "**/*$py.class",
    ])
    
    # Find all .gitignore files
    for root, _, files in os.walk(repo_path):
        if '.gitignore' in files:
            gitignore_path = Path(root) / '.gitignore'
            with open(gitignore_path, 'r', encoding='utf-8') as file:
                # Add each non-empty line as a pattern
                for line in file:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        patterns.append(line)
    
    return pathspec.PathSpec.from_lines('gitwildmatch', patterns)


def should_exclude_file(file_path: str, rel_path: str) -> bool:
    """
    Determine if a file should be excluded based on its name or path.
    
    Args:
        file_path: The absolute file path.
        rel_path: The relative path from the repo root.
        
    Returns:
        True if the file should be excluded, False otherwise.
    """
    # Common patterns to exclude
    excluded_patterns = [
        # Package management files
        "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb",
        "Gemfile.lock", "Cargo.lock", "composer.lock", "poetry.lock",
        
        # Build output directories (usually covered by .gitignore but adding as backup)
        "dist/", "build/", "out/", "target/", ".next/", ".nuxt/", ".output/",
        
        # Config files that aren't essential for code understanding
        ".eslintrc", ".prettierrc", ".stylelintrc", ".editorconfig", ".browserslistrc",
        "tsconfig.json", "jsconfig.json", "babel.config", "webpack.config",
        "vite.config", "rollup.config", "postcss.config", "tailwind.config",
        ".npmrc", ".yarnrc", ".nvmrc", ".ruby-version", ".python-version",
        
        # IDE and editor files
        ".vscode/", ".idea/", ".vs/", "*.iml", "*.sublime-project", "*.sublime-workspace",
        
        # Miscellaneous files
        "LICENSE", "CHANGELOG", "CODEOWNERS", ".gitattributes", ".github/"
    ]
    
    # File extensions to exclude
    excluded_extensions = [
        ".map", ".min.js", ".min.css", ".bundle.js", ".bundle.css",
        ".log", ".pid", ".seed", ".gz", ".zip", ".tar", ".rar",
        ".tmp", ".temp", ".swp", ".swo",
        ".ico", ".svg", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp",
        ".psd", ".ai", ".sketch", ".fig", ".xcf",
        ".wav", ".mp3", ".ogg", ".mp4", ".webm", ".avi", ".mov",
        ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".pdf"
    ]
    
    # Check filename
    filename = os.path.basename(file_path)
    
    # Check against excluded patterns
    for pattern in excluded_patterns:
        # If pattern ends with /, it's a directory pattern
        if pattern.endswith('/'):
            if f"{pattern[:-1]}/" in rel_path + "/":
                return True
        # Otherwise it's a file pattern (support prefix matching with *)
        elif pattern.startswith('*'):
            if filename.endswith(pattern[1:]):
                return True
        # Exact match
        elif filename == pattern or filename.startswith(f"{pattern}."):
            return True
    
    # Check file extension
    file_ext = os.path.splitext(filename)[1].lower()
    if file_ext in excluded_extensions:
        return True
    
    # Special case for dot files (.env, .gitignore, etc.)
    if filename.startswith('.') and not (
        # Make exceptions for source files with dot prefixes
        filename.endswith('.js') or
        filename.endswith('.ts') or
        filename.endswith('.py') or
        filename.endswith('.rb') or
        filename.endswith('.jsx') or
        filename.endswith('.tsx')
    ):
        return True
    
    return False


def should_include_file(file_path: str) -> bool:
    """
    Determine if a file should be included based on its extension.
    
    Args:
        file_path: The file path.
        
    Returns:
        True if the file should be included, False otherwise.
    """
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
    
    filename = os.path.basename(file_path)
    file_ext = os.path.splitext(filename)[1].lower()
    
    # Always include important filenames
    for name in important_filenames:
        if filename.startswith(name):
            return True
    
    # Include based on extension
    return file_ext in included_extensions


def get_relevant_files_with_content(repo_path: Path):
    """
    Get all relevant files with their content from a repository.
    Also track ignored files.
    
    Args:
        repo_path: The path to the repository.
        
    Returns:
        A tuple containing:
        - A list of tuples (file_path, content) for included files
        - A list of paths for ignored files
    """
    gitignore_spec = parse_gitignore(repo_path)
    included_files = []
    ignored_files = []
    
    for root, _, files in os.walk(repo_path):
        rel_root = os.path.relpath(root, repo_path)
        
        for file in files:
            rel_path = os.path.join(rel_root, file)
            abs_path = os.path.join(root, file)
            
            # Skip files that match .gitignore patterns
            if gitignore_spec.match_file(rel_path):
                ignored_files.append(Path(abs_path))
                continue
            
            # Further filter with our custom rules
            if should_exclude_file(abs_path, rel_path):
                ignored_files.append(Path(abs_path))
                continue
            
            # Ensure it's a file type we want to include
            if not should_include_file(abs_path):
                ignored_files.append(Path(abs_path))
                continue
            
            try:
                with open(abs_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                
                # Skip empty files
                if not content.strip():
                    ignored_files.append(Path(abs_path))
                    continue
                
                included_files.append((Path(abs_path), content))
            except (UnicodeDecodeError, PermissionError, IsADirectoryError):
                # Skip binary files or files we can't read
                ignored_files.append(Path(abs_path))
    
    return included_files, ignored_files