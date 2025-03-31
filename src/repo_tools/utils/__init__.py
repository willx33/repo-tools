"""Utilities package for repo tools.

This package provides utility functions shared between CLI and WebUI components.
"""

# API version to track compatibility
__api_version__ = '1.0.0'

# Re-export the public APIs
from repo_tools.utils.git import find_git_repos, get_repo_name, get_relevant_files_with_content, parse_gitignore
from repo_tools.utils.clipboard import copy_to_clipboard
from repo_tools.utils.notifications import show_toast