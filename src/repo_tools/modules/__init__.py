"""Modules package for repo tools.

This package provides a unified API for both CLI and WebUI components
to access the core functionality of repo tools.
"""

# Re-export the public APIs that can be used by both CLI and WebUI
from repo_tools.modules.context_copier import repo_context_copier
from repo_tools.modules.github_context_copier import github_repo_context_copier, extract_github_repo_url, clone_github_repo

# Define a version to track API compatibility
__api_version__ = '1.0.0'

# Define a stable API for accessing repo tools functionality
def get_local_repo_context(repo_path=None, **kwargs):
    """
    Get context from a local repository.
    
    Args:
        repo_path: Path to the repository (optional - will prompt if not provided)
        **kwargs: Additional arguments to pass to the underlying implementation
        
    Returns:
        A tuple containing the status (True for success, False for failure),
        and if successful, the formatted context.
    """
    from repo_tools.modules.context_copier import repo_context_copier
    if repo_path is not None:
        return repo_context_copier(repo_path=repo_path, **kwargs)
    else:
        return repo_context_copier(**kwargs)

def get_github_repo_context(repo_url=None, **kwargs):
    """
    Get context from a GitHub repository.
    
    Args:
        repo_url: URL of the GitHub repository (optional - will prompt if not provided)
        **kwargs: Additional arguments to pass to the underlying implementation
        
    Returns:
        A tuple containing the status (True for success, False for failure),
        and if successful, the formatted context.
    """
    from repo_tools.modules.github_context_copier import github_repo_context_copier
    if repo_url is not None:
        return github_repo_context_copier(repo_url=repo_url, **kwargs)
    else:
        return github_repo_context_copier(**kwargs)

def process_repository_files(repo_path):
    """
    Process files in a repository and get their content.
    
    Args:
        repo_path: Path to the repository
        
    Returns:
        A tuple containing included files with content and ignored files.
    """
    from repo_tools.utils.git import get_relevant_files_with_content
    return get_relevant_files_with_content(repo_path)