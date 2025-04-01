"""XML parser module for handling o1-generated XML code changes.

This module provides functionality to parse XML content from o1 and apply the changes
to a specified repository directory.
"""

import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
import xml.etree.ElementTree as ET
from xml.dom import minidom

# Set up logging
logger = logging.getLogger(__name__)

class XMLParserError(Exception):
    """Exception raised for errors in the XML parser."""
    pass

class FileChange:
    """Class representing a file change from parsed XML."""
    
    def __init__(
        self, 
        operation: str, 
        path: str, 
        code: Optional[str] = None, 
        summary: Optional[str] = None
    ):
        """Initialize a FileChange object.
        
        Args:
            operation: The operation type (CREATE, UPDATE, DELETE)
            path: The file path relative to the repository root
            code: The file content (for CREATE and UPDATE operations)
            summary: A summary of the changes (optional)
        """
        self.operation = operation.upper()
        self.path = path
        self.code = code
        self.summary = summary
    
    def __repr__(self) -> str:
        """Return a string representation of the FileChange object."""
        return f"FileChange({self.operation}, {self.path})"

def parse_xml_string(xml_string: str) -> List[FileChange]:
    """Parse an XML string into a list of FileChange objects.
    
    Args:
        xml_string: The XML string to parse
        
    Returns:
        A list of FileChange objects representing the changes
        
    Raises:
        XMLParserError: If the XML string is invalid or cannot be parsed
    """
    # Try to extract XML content from code blocks if necessary
    xml_string = extract_xml_from_markdown(xml_string)
    
    try:
        # Use minidom for parsing (more lenient than ElementTree)
        dom = minidom.parseString(xml_string)
        
        # Find the changed_files node
        changed_files_nodes = dom.getElementsByTagName("changed_files")
        if not changed_files_nodes:
            raise XMLParserError("No 'changed_files' element found in XML")
        
        changed_files_node = changed_files_nodes[0]
        
        # Extract file nodes
        file_nodes = changed_files_node.getElementsByTagName("file")
        if not file_nodes:
            raise XMLParserError("No 'file' elements found in XML")
        
        # Parse each file node
        changes = []
        for file_node in file_nodes:
            # Extract file operation
            operation_nodes = file_node.getElementsByTagName("file_operation")
            if not operation_nodes:
                logger.warning("No 'file_operation' element found in file node, skipping")
                continue
            operation = operation_nodes[0].firstChild.nodeValue.strip()
            
            # Extract file path
            path_nodes = file_node.getElementsByTagName("file_path")
            if not path_nodes:
                logger.warning("No 'file_path' element found in file node, skipping")
                continue
            path = path_nodes[0].firstChild.nodeValue.strip()
            
            # Extract file content (if available)
            code = None
            code_nodes = file_node.getElementsByTagName("file_code")
            if code_nodes and code_nodes[0].firstChild:
                code = code_nodes[0].firstChild.nodeValue
            
            # Extract file summary (if available)
            summary = None
            summary_nodes = file_node.getElementsByTagName("file_summary")
            if summary_nodes and summary_nodes[0].firstChild:
                summary = summary_nodes[0].firstChild.nodeValue.strip()
            
            # Create FileChange object
            change = FileChange(operation, path, code, summary)
            changes.append(change)
        
        return changes
    
    except Exception as e:
        logger.error(f"Error parsing XML: {str(e)}")
        raise XMLParserError(f"Failed to parse XML: {str(e)}")

def extract_xml_from_markdown(text: str) -> str:
    """Extract XML content from markdown code blocks if present.
    
    Args:
        text: The text that may contain markdown-formatted XML
        
    Returns:
        The extracted XML content or the original text if no code blocks found
    """
    # Look for markdown code blocks (```xml ... ```)
    code_block_pattern = r"```(?:xml)?\s*\n(.*?)<code_changes>.*?</code_changes>.*?\n```"
    match = re.search(code_block_pattern, text, re.DOTALL)
    
    if match:
        # Extract content inside the code block
        xml_content = match.group(1)
        
        # Further extract just the <code_changes> element
        code_changes_pattern = r"(<code_changes>.*?</code_changes>)"
        code_changes_match = re.search(code_changes_pattern, xml_content, re.DOTALL)
        
        if code_changes_match:
            return code_changes_match.group(1)
    
    # If not found in code blocks, try directly extracting the <code_changes> element
    direct_pattern = r"(<code_changes>.*?</code_changes>)"
    direct_match = re.search(direct_pattern, text, re.DOTALL)
    
    if direct_match:
        return direct_match.group(1)
    
    # Return the original text if no patterns matched
    return text

def apply_changes(changes: List[FileChange], repo_path: str) -> List[Tuple[FileChange, bool, Optional[str]]]:
    """Apply a list of FileChange objects to a repository.
    
    Args:
        changes: A list of FileChange objects
        repo_path: The absolute path to the repository root
        
    Returns:
        A list of tuples containing (FileChange, success, error_message)
    """
    results = []
    
    for change in changes:
        success = True
        error_message = None
        
        try:
            full_path = os.path.join(repo_path, change.path)
            
            if change.operation == "CREATE":
                if change.code is None:
                    error_message = "No file content provided for CREATE operation"
                    success = False
                    continue
                
                # Ensure directory exists
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                
                # Write the file
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(change.code)
            
            elif change.operation == "UPDATE":
                if change.code is None:
                    error_message = "No file content provided for UPDATE operation"
                    success = False
                    continue
                
                # Ensure directory exists
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                
                # Write the file
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(change.code)
            
            elif change.operation == "DELETE":
                # Check if file exists before deleting
                if os.path.exists(full_path):
                    os.remove(full_path)
                else:
                    logger.warning(f"File {full_path} does not exist, cannot delete")
            
            else:
                error_message = f"Unknown operation: {change.operation}"
                success = False
        
        except Exception as e:
            success = False
            error_message = str(e)
            logger.error(f"Error applying change to {change.path}: {str(e)}")
        
        results.append((change, success, error_message))
    
    return results

def preview_changes(changes: List[FileChange], repo_path: str) -> List[Dict[str, Any]]:
    """Generate a preview of the changes to be applied.
    
    Args:
        changes: A list of FileChange objects
        repo_path: The absolute path to the repository root
        
    Returns:
        A list of dictionaries with preview information
    """
    previews = []
    
    for change in changes:
        preview = {
            "operation": change.operation,
            "path": change.path,
            "exists": False,
            "has_diff": False,
            "diff": None,
            "summary": change.summary
        }
        
        full_path = os.path.join(repo_path, change.path)
        file_exists = os.path.exists(full_path)
        preview["exists"] = file_exists
        
        if change.operation == "CREATE":
            preview["status"] = "Will create new file"
            if file_exists:
                preview["warning"] = "File already exists and will be overwritten"
                preview["has_diff"] = True
                # We could add a diff here between existing and new content
        
        elif change.operation == "UPDATE":
            if file_exists:
                preview["status"] = "Will update existing file"
                # We could add a diff here between existing and new content
                preview["has_diff"] = True
            else:
                preview["status"] = "Will create new file (marked as UPDATE)"
                preview["warning"] = "File doesn't exist but will be created"
        
        elif change.operation == "DELETE":
            if file_exists:
                preview["status"] = "Will delete file"
            else:
                preview["status"] = "Cannot delete (file doesn't exist)"
                preview["warning"] = "File doesn't exist"
        
        previews.append(preview)
    
    return previews 