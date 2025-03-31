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
    
    # Add default ignored patterns (even if not in .gitignore)
    patterns.extend([
        # Git directories
        ".git/",
        
        # Node.js
        "node_modules/",
        "**/node_modules/**",
        
        # Python
        "**/__pycache__/",
        "**/*.py[cod]",
        "**/*$py.class",
        "venv/",
        "env/",
        ".env/",
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
    # Always include .env files regardless of location.
    filename = os.path.basename(file_path)
    # Enhanced .env detection to catch all variations (.env.local, .env.development, etc.)
    if filename == ".env" or filename.startswith(".env.") or ".env" in filename:
        return False

    # CRITICAL: Dependency directories to exclude completely (with trailing slash to ensure directory matching)
    dependency_dirs = [
        # Node.js
        "node_modules/",
        # Python
        "venv/", "env/", ".venv/", ".tox/", "site-packages/", "dist-packages/", "__pycache__/",
        # Ruby
        "vendor/bundle/", "vendor/ruby/", ".bundle/",
        # Java/Maven/Gradle
        "target/", "build/lib/", ".gradle/",
        # PHP
        "vendor/", "composer/",
        # Go
        "vendor/", "pkg/",
        # Rust
        "target/", "cargo/",
        # Swift/iOS
        "Pods/", "Carthage/",
        # .NET
        "bin/", "obj/", "packages/",
        # General
        "third_party/", "third-party/", "external/", "deps/"
    ]
    
    # Check for dependency directories
    rel_path_with_slash = f"{rel_path}/" if rel_path != "." else "/"
    for dep_dir in dependency_dirs:
        # If the dependency directory appears anywhere in the path
        if dep_dir in rel_path_with_slash:
            return True
    
    # Common patterns to exclude
    excluded_patterns = [
        # Package management files
        "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb",
        "Gemfile.lock", "Cargo.lock", "composer.lock", "poetry.lock",
        
        # Build output directories (usually covered by .gitignore but adding as backup)
        "dist/", "build/", "out/", "target/", ".next/", ".nuxt/", ".output/",
        
        # IDE and editor files
        ".vscode/", ".idea/", ".vs/", "*.iml", "*.sublime-project", "*.sublime-workspace",
        
        # Miscellaneous files
        "CHANGELOG", "CODEOWNERS", ".gitattributes", ".github/"
    ]
    
    # File extensions to exclude - only exclude binary and non-code files
    excluded_extensions = [
        # Source maps
        ".map",
        # Minified/bundled
        ".min.js", ".min.css", ".bundle.js", ".bundle.css",
        # Logs and temp files
        ".log", ".pid", ".seed", ".tmp", ".temp", ".swp", ".swo",
        # Binary
        ".exe", ".dll", ".so", ".dylib", ".class", ".jar", ".war", ".ear", 
        # Archives
        ".gz", ".zip", ".tar", ".rar", ".7z", 
        # Images
        ".ico", ".svg", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp",
        ".psd", ".ai", ".sketch", ".fig", ".xcf",
        # Media
        ".wav", ".mp3", ".ogg", ".mp4", ".webm", ".avi", ".mov",
        # Documents
        ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".pdf"
    ]
    
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
    
    # Special case for dot files (.gitignore, etc.) - we need to be careful not to exclude important config files
    if filename.startswith('.') and not (
        # Don't exclude any .env files
        filename == ".env" or filename.startswith(".env.") or ".env" in filename or
        # Don't exclude dotfiles with common code extensions
        filename.endswith('.js') or filename.endswith('.jsx') or 
        filename.endswith('.ts') or filename.endswith('.tsx') or
        filename.endswith('.py') or filename.endswith('.rb') or
        filename.endswith('.go') or filename.endswith('.rs') or
        filename.endswith('.java') or filename.endswith('.kt') or
        filename.endswith('.c') or filename.endswith('.cpp') or filename.endswith('.h') or
        filename.endswith('.cs') or filename.endswith('.fs') or
        filename.endswith('.php') or filename.endswith('.swift') or
        # Don't exclude important config files
        filename == ".gitignore" or filename == ".dockerignore" or
        filename == ".babelrc" or filename == ".eslintrc.js" or
        filename == ".prettierrc" or filename == ".editorconfig" or
        filename.endswith('.json') or filename.endswith('.yaml') or filename.endswith('.yml') or
        filename.endswith('.xml') or filename.endswith('.toml')
    ):
        return True
    
    # Check file size limit to avoid huge files - 1MB limit
    try:
        if os.path.getsize(file_path) > 1024 * 1024:
            return True
    except (OSError, IOError):
        # If we can't check the size, assume it's ok
        pass
    
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
        ".vue", ".svelte", ".astro", ".hbs", ".ejs", ".pug",
        # Backend
        ".py", ".rb", ".php", ".java", ".go", ".rs", ".c", ".cpp", ".h", ".hpp",
        ".cs", ".fs", ".swift", ".kt", ".kts", ".scala", ".clj", ".ex", ".exs",
        ".dart", ".lua", ".pl", ".pm", ".groovy", ".erl", ".elm", ".hs",
        # Config/Data
        ".json", ".yml", ".yaml", ".toml", ".ini", ".env.example", ".sql", ".graphql", ".gql",
        ".xml", ".csv", ".tsv", ".proto", ".mdx", ".nix", ".bat", ".sh", ".ps1",
        # Documentation
        ".md", ".mdx", ".rst", ".txt", ".asciidoc", ".adoc",
        # Other source formats
        ".prisma", ".styl", ".hcl", ".tf", ".r"
    ]
    
    # Special files to always include regardless of extension
    important_filenames = [
        "README", "CONTRIBUTING", "ARCHITECTURE", "CODEOWNERS", "Dockerfile", "docker-compose.yml",
        "Makefile", "rakefile", "Rakefile", "CMakeLists.txt", "requirements.txt",
        "go.mod", "go.sum", "build.gradle", "pom.xml", "build.sbt", "Cargo.toml",
        "package.json", "tsconfig.json", "eslintrc", "prettierrc", "babelrc", 
        "webpack.config", "vite.config", "rollup.config", "nginx.conf"
    ]
    
    filename = os.path.basename(file_path)
    file_ext = os.path.splitext(filename)[1].lower()
    
    # Always include important filenames
    for name in important_filenames:
        if filename.startswith(name) or name.lower() in filename.lower():
            return True

    # Always include .env files regardless of extension/naming
    if filename == ".env" or filename.startswith(".env.") or ".env" in filename:
        return True
    
    # Include based on extension - be generous with what we include
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
            
            # Allow .env files (.env, .env.local, etc.) even if matched in .gitignore
            is_env_file = file == ".env" or file.startswith(".env.") or ".env" in file
            if not is_env_file and gitignore_spec.match_file(rel_path):
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
