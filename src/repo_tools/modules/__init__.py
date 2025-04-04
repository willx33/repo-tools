"""Modules package for repo tools.

This package provides a unified API for both CLI and WebUI components
to access the core functionality of repo tools.
"""

# Re-export the public APIs that can be used by both CLI and WebUI
from repo_tools.modules.context_copier import repo_context_copier
from repo_tools.modules.github_context_copier import github_repo_context_copier, extract_github_repo_url, clone_github_repo
from repo_tools.modules.xml_parser import parse_xml_string, parse_xml, parse_xml_preview, process_xml_changes, generate_xml_from_changes, validate_changes, XMLParserError

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

def process_xml_changes(xml_string, repo_path):
    """
    Parse XML content and apply changes to a repository.
    
    Args:
        xml_string: The XML string to parse
        repo_path: Path to the target repository
        
    Returns:
        A list of tuples containing the file changes, success status, and error messages (if any)
    
    Raises:
        XMLParserError: If the XML string is invalid or cannot be parsed
    """
    from repo_tools.modules.xml_parser import parse_xml_string, apply_changes
    changes = parse_xml_string(xml_string)
    return apply_changes(changes, repo_path)

def process_xml_changes_legacy(xml_string, repo_path):
    """
    Parse XML content and apply changes to a repository.
    
    Args:
        xml_string: The XML string to parse
        repo_path: Path to the target repository
        
    Returns:
        A list of tuples containing the file changes, success status, and error messages (if any)
    
    Raises:
        XMLParserError: If the XML string is invalid or cannot be parsed
    """
    from repo_tools.modules.xml_parser import parse_xml
    return parse_xml(xml_string, repo_path)

def preview_xml_changes(xml_string, repo_path):
    """
    Parse XML content and generate a preview of changes.
    
    Args:
        xml_string: The XML string to parse
        repo_path: Path to the target repository
        
    Returns:
        A list of dictionaries with preview information
    
    Raises:
        XMLParserError: If the XML string is invalid or cannot be parsed
    """
    from repo_tools.modules.xml_parser import parse_xml_preview
    return parse_xml_preview(xml_string, repo_path)