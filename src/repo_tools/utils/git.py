"""Git utilities for repo tools."""

import os
from pathlib import Path
from typing import List, Tuple, Set
import pathspec
import logging # Added for potential logging

logger = logging.getLogger(__name__) # Added logger


def find_git_repos(directory: Path) -> List[Path]:
    """
    Find git repositories in the given directory.

    Args:
        directory: The directory to search in.

    Returns:
        A list of paths to git repositories.
    """
    repos = []
    # Ensure input is Path object and directory exists
    if not isinstance(directory, Path):
        directory = Path(directory)
    if not directory.is_dir():
        logger.warning(f"Provided directory '{directory}' is not valid. Cannot find git repos.")
        return repos

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
    # Ensure input is Path object
    if not isinstance(repo_path, Path):
        repo_path = Path(repo_path)
    return repo_path.name


def parse_gitignore(repo_path: Path) -> pathspec.PathSpec:
    """
    Parse all .gitignore files in a repository, including default ignores.

    Args:
        repo_path: The Path object to the repository.

    Returns:
        A PathSpec object representing the combined .gitignore rules.
    """
    patterns = []

    # Add default ignored patterns (even if not in .gitignore)
    # Using POSIX separators as gitignore typically uses them
    patterns.extend([
        # Git directories
        ".git/",

        # Node.js
        "node_modules/",
        "**/node_modules/**",

        # Python
        "**/__pycache__/",
        "*.py[cod]",
        "*$py.class",
        "venv/",
        "env/",
        ".env", # Specific .env files handled later
        ".venv/",

        # Java/Maven/Gradle
        "target/",
        "build/",

        # Ruby
        "vendor/bundle/",

        # PHP
        "vendor/",

        # .NET
        "bin/",
        "obj/",

        # General dependency directories
        "third_party/",
        "third-party/",
        "external/",
        "deps/",
    ])

    # Find all .gitignore files using rglob
    try:
        for gitignore_path in repo_path.rglob('.gitignore'):
             if gitignore_path.is_file(): # Make sure it's a file
                 try:
                     with open(gitignore_path, 'r', encoding='utf-8', errors='ignore') as file:
                         # Calculate relative dir for nested gitignores
                         relative_dir = gitignore_path.parent.relative_to(repo_path)
                         for line in file:
                             line = line.strip()
                             if line and not line.startswith('#'):
                                 # Prepend relative directory path if the pattern is not absolute
                                 # Use as_posix() for consistent forward slashes
                                 if not line.startswith('/'):
                                     pattern = (relative_dir / line).as_posix()
                                 else:
                                     pattern = line # Absolute patterns start from repo root
                                 patterns.append(pattern)
                 except IOError as e:
                     logger.warning(f"Could not read .gitignore file {gitignore_path}: {e}")
                 except Exception as e:
                     logger.error(f"Error processing .gitignore file {gitignore_path}: {e}")
    except Exception as e:
       logger.error(f"Error searching for .gitignore files in {repo_path}: {e}")


    return pathspec.PathSpec.from_lines(pathspec.patterns.GitWildMatchPattern, patterns)


# Modified to accept Path objects and use pathlib methods
def should_exclude_file(file_path: Path, rel_path: Path) -> bool:
    """
    Determine if a file should be excluded based on its name or path.

    Args:
        file_path: The absolute Path object for the file.
        rel_path: The Path object relative to the repo root.

    Returns:
        True if the file should be excluded, False otherwise.
    """
    filename = file_path.name # Use Path.name

    # Always include .env files regardless of location.
    # Enhanced .env detection to catch all variations (.env.local, .env.development, etc.)
    if filename == ".env" or filename.startswith(".env.") or ".env" in filename:
        return False

    # CRITICAL: Dependency directories to exclude completely
    # Check using path components for cross-platform reliability
    dependency_dir_names = {
        # Node.js
        "node_modules",
        # Python
        "venv", "env", ".venv", ".tox", "site-packages", "dist-packages", "__pycache__",
        # Ruby
        "vendor", # Often includes 'bundle', 'ruby' etc.
        ".bundle",
        # Java/Maven/Gradle
        "target", "build", ".gradle", # Added 'build' here
        # PHP (vendor is already included)
        "composer",
        # Go (vendor is already included)
        "pkg",
        # Rust
        "target", "cargo", # Usually target/debug or target/release
        # Swift/iOS
        "Pods", "Carthage",
        # .NET
        "bin", "obj", "packages",
        # General
        "third_party", "third-party", "external", "deps"
    }
    # Check if any parent directory part matches the exclusion list
    # Use rel_path.parts to reliably check components
    if any(part in dependency_dir_names for part in rel_path.parent.parts):
        return True

    # Common patterns to exclude (filenames)
    excluded_filenames = {
        # Package management files
        "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb",
        "Gemfile.lock", "Cargo.lock", "composer.lock", "poetry.lock",

        # Build output directories (usually covered by .gitignore but adding as backup)
        # Directories are better handled by the dependency_dir_names check above
        # "dist/", "build/", "out/", "target/", ".next/", ".nuxt/", ".output/",

        # IDE and editor files
        ".vscode", ".idea", ".vs", # Check full names, directories handled above
        "*.iml", "*.sublime-project", "*.sublime-workspace", # Check suffixes

        # Miscellaneous files (check full names)
        "CHANGELOG", "CODEOWNERS", ".gitattributes",
        # Let .github directory contents be decided by should_include_file
    }

    # File extensions to exclude - only exclude binary and non-code files
    excluded_extensions = {
        # Source maps
        ".map",
        # Minified/bundled (often duplicates, less useful for context)
        ".min.js", ".min.css", ".bundle.js", ".bundle.css",
        # Logs and temp files
        ".log", ".pid", ".seed", ".tmp", ".temp", ".swp", ".swo",
        # Binary executables/libraries
        ".exe", ".dll", ".so", ".dylib", ".class", ".jar", ".war", ".ear", ".pyc", ".pyo", ".o", ".a",
        # Archives
        ".gz", ".zip", ".tar", ".rar", ".7z", ".tgz", ".bz2",
        # Images
        ".ico", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp",
        ".psd", ".ai", ".sketch", ".fig", ".xcf",
        # Media
        ".wav", ".mp3", ".ogg", ".mp4", ".webm", ".avi", ".mov",
        # Documents
        ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".pdf"
    }

    # Check against excluded patterns/filenames
    # Use Path.suffix for extension matching
    file_ext = file_path.suffix.lower() # Includes the dot, e.g. '.py'
    if filename in excluded_filenames or file_ext in excluded_extensions:
        return True
    # Check suffix patterns like *.iml
    if filename.endswith(('.iml', '.sublime-project', '.sublime-workspace')):
         return True


    # Special case for dot files (.gitignore, etc.) - be careful not to exclude important config files
    if filename.startswith('.') and not (
        # Don't exclude any .env files (already covered, but explicit here)
        filename == ".env" or filename.startswith(".env.") or ".env" in filename or
        # Don't exclude important config/code dotfiles by checking extension or full name
        file_ext in {'.js', '.jsx', '.ts', '.tsx', '.py', '.rb', '.go', '.rs', '.java', '.kt', '.c', '.cpp', '.h', '.cs', '.fs', '.php', '.swift', '.json', '.yaml', '.yml', '.xml', '.toml', '.sh', '.bash', '.zsh'} or
        filename in {".gitignore", ".dockerignore", ".gitattributes", ".gitmodules", ".babelrc", ".eslintrc", ".prettierrc", ".editorconfig"}
    ):
        return True

    # Check file size limit to avoid huge files - 1MB limit
    try:
        if file_path.stat().st_size > 1 * 1024 * 1024: # 1 MB
            return True
    except (OSError, IOError) as e:
        # If we can't check the size, log warning but don't exclude based on this rule
        logger.warning(f"Could not check size for {file_path}: {e}")
        pass

    return False # If no exclusion rule matched


# Modified to accept Path object and use pathlib methods
def should_include_file(file_path: Path) -> bool:
    """
    Determine if a file should be included based on its extension or name.
    This acts as a secondary filter *after* gitignore and `should_exclude_file`.

    Args:
        file_path: The Path object for the file.

    Returns:
        True if the file should be included, False otherwise.
    """
    filename = file_path.name
    file_ext = file_path.suffix.lower() # Includes the dot, e.g. '.py'

    # File extensions that are likely source code or important config
    included_extensions = {
        # Web
        ".js", ".jsx", ".ts", ".tsx", ".html", ".htm", ".css", ".scss", ".sass", ".less",
        ".vue", ".svelte", ".astro", ".hbs", ".ejs", ".pug",
        # Backend
        ".py", ".rb", ".php", ".java", ".go", ".rs", ".c", ".cpp", ".h", ".hpp",
        ".cs", ".fs", ".swift", ".kt", ".kts", ".scala", ".clj", ".ex", ".exs",
        ".dart", ".lua", ".pl", ".pm", ".groovy", ".erl", ".elm", ".hs",
        # Config/Data
        ".json", ".yml", ".yaml", ".toml", ".ini", ".env.example", ".sql", ".graphql", ".gql",
        ".xml", ".csv", ".tsv", ".proto", ".mdx", ".nix", ".bat", ".sh", ".ps1",
        # Documentation
        ".md", ".rst", ".txt", ".asciidoc", ".adoc",
        # Other source formats
        ".prisma", ".styl", ".hcl", ".tf", ".r",
        # Include SVG as it's often part of UI code
        ".svg",
    }

    # Special files to always include regardless of extension
    important_filenames = {
        "readme", "contributing", "architecture", "codeowners", "dockerfile", "docker-compose.yml", "docker-compose.yaml",
        "makefile", "rakefile", "cmakelists.txt", "requirements.txt",
        "go.mod", "go.sum", "build.gradle", "pom.xml", "build.sbt", "cargo.toml",
        "package.json", "tsconfig.json", "eslintrc", "prettierrc", "babelrc",
        "webpack.config", "vite.config", "rollup.config", "nginx.conf",
        # Dotfiles previously allowed in should_exclude_file
        ".gitignore", ".dockerignore", ".gitattributes", ".gitmodules",
        ".babelrc", ".eslintrc.js", ".eslintrc.json", ".eslintrc.yaml", ".eslintrc.yml",
        ".prettierrc", ".prettierrc.js", ".prettierrc.json", ".prettierrc.yaml", ".prettierrc.yml",
        ".stylelintrc", ".stylelintrc.json",
        ".bashrc", ".zshrc", ".profile",
        ".npmrc", ".yarnrc", ".yarnrc.yml",
        ".editorconfig",
    }
    # Include .env files explicitly here too, although handled by should_exclude
    if filename == ".env" or filename.startswith(".env.") or ".env" in filename:
        return True

    # Always include important filenames (case-insensitive check)
    if filename.lower() in important_filenames:
        return True
    # Check prefix matches for files like README.md
    for name in important_filenames:
        if filename.lower().startswith(name):
            return True

    # Include based on extension
    return file_ext in included_extensions


# Modified to use pathlib internally for paths passed to filters
def get_relevant_files_with_content(repo_path: Path):
    """
    Get all relevant files with their content from a repository.
    Also track ignored files.

    Args:
        repo_path: The path to the repository (as a Path object).

    Returns:
        A tuple containing:
        - A list of tuples (file_path: Path, content: str) for included files
        - A list of paths (Path objects) for ignored files
    """
    if not isinstance(repo_path, Path):
         repo_path = Path(repo_path) # Ensure it's a Path object

    gitignore_spec = parse_gitignore(repo_path)
    included_files: List[Tuple[Path, str]] = []
    ignored_files_set: Set[Path] = set() # Use set for efficiency

    processed_paths = set() # Avoid processing the same file path twice

    for root, _, files in os.walk(repo_path):
        current_root = Path(root) # Convert root to Path

        # --- Directory Filtering (optional optimization) ---
        # Skip .git directories early
        if '.git' in current_root.parts:
             continue
        # You could add more directory skips here if needed (e.g., node_modules)
        # but the file-level checks below handle it robustly.

        for file in files:
            abs_path = current_root / file # Use pathlib for joining
            if abs_path in processed_paths:
                continue
            processed_paths.add(abs_path)

            if not abs_path.is_file(): # Skip directories, symlinks, etc.
                continue

            try:
                # Use pathlib for relative path calculation
                rel_path = abs_path.relative_to(repo_path)
                # Use POSIX path for gitignore matching consistency
                rel_path_posix = rel_path.as_posix()
            except ValueError:
                # Should not happen if os.walk stays within repo_path, but safety check
                logger.warning(f"File {abs_path} is outside repository {repo_path}. Skipping.")
                continue

            # --- Filtering Logic ---
            # 1. Check gitignore (allow .env files)
            is_env_file = abs_path.name == ".env" or abs_path.name.startswith(".env.")
            if not is_env_file and gitignore_spec.match_file(rel_path_posix):
                ignored_files_set.add(abs_path)
                continue

            # 2. Check custom exclusion rules (using Path objects)
            if should_exclude_file(abs_path, rel_path):
                ignored_files_set.add(abs_path)
                continue

            # 3. Check custom inclusion rules (using Path objects)
            if not should_include_file(abs_path):
                ignored_files_set.add(abs_path)
                continue

            # 4. Try reading the file content
            try:
                with open(abs_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()

                # Skip empty files
                if not content.strip():
                    ignored_files_set.add(abs_path)
                    continue

                # If all checks pass, add to included files (store Path object)
                included_files.append((abs_path, content))

            except (UnicodeDecodeError, IsADirectoryError) as read_error:
                # Skip binary files or files we can't read
                # logger.debug(f"Ignoring binary or unreadable file {rel_path_posix}: {read_error}")
                ignored_files_set.add(abs_path)
            except OSError as e:
                # Handle other OS errors like PermissionError
                logger.warning(f"Could not read file {abs_path}: {e}")
                ignored_files_set.add(abs_path)

    # Convert set of ignored files back to a list
    ignored_files_list = list(ignored_files_set)

    return included_files, ignored_files_list